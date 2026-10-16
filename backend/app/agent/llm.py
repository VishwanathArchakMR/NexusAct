"""LLM provider abstraction for NexusAct adaptive investigation loop.

Supports:
- Local Ollama (preferred local-first provider)
- OpenAI-compatible endpoints
- FakeLLMProvider (for deterministic unit tests)
- NoneLLMProvider (honest fallback when no model is configured)
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel, Field

from backend.app.core.config import settings

logger = logging.getLogger("nexusact.agent.llm")


class LLMToolCall(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    reasoning: str = ""


class LLMDecision(BaseModel):
    action: str = Field(..., description="'call_tool' or 'finish'")
    tool_call: Optional[LLMToolCall] = None
    finish_summary: Optional[str] = None
    suggested_action_title: Optional[str] = None
    suggested_action_body: Optional[str] = None


class BaseLLMProvider(ABC):
    """Abstract interface for model providers driving the adaptive investigation."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    async def decide_next_step(
        self,
        question: str,
        target_module_id: str,
        available_tools: List[Dict[str, Any]],
        investigation_history: List[Dict[str, Any]],
        remaining_budget: int,
    ) -> LLMDecision:
        """Determines the next tool to invoke or decides to finish investigation."""
        pass


class NoneLLMProvider(BaseLLMProvider):
    """Honest fallback when no model provider is configured."""

    @property
    def name(self) -> str:
        return "none"

    @property
    def is_available(self) -> bool:
        return False

    async def decide_next_step(
        self,
        question: str,
        target_module_id: str,
        available_tools: List[Dict[str, Any]],
        investigation_history: List[Dict[str, Any]],
        remaining_budget: int = 0,
    ) -> LLMDecision:

        raise RuntimeError(
            "No LLM provider is configured. The adaptive investigation agent requires a configured model "
            "(e.g. Ollama or OpenAI). Direct graph queries and MCP tools remain fully functional."
        )


class FakeLLMProvider(BaseLLMProvider):
    """Deterministic scripted mock provider for unit tests and protocol evaluation."""

    def __init__(self, predefined_decisions: Optional[List[LLMDecision]] = None):
        self._decisions = list(predefined_decisions or [])
        self._index = 0

    @property
    def name(self) -> str:
        return "fake"

    @property
    def is_available(self) -> bool:
        return True

    def add_decision(self, decision: LLMDecision) -> None:
        self._decisions.append(decision)

    async def decide_next_step(
        self,
        question: str,
        target_module_id: str,
        available_tools: List[Dict[str, Any]],
        investigation_history: List[Dict[str, Any]],
        remaining_budget: int,
    ) -> LLMDecision:
        if self._index < len(self._decisions):
            decision = self._decisions[self._index]
            self._index += 1
            return decision

        # Default fallback decision if none remaining
        return LLMDecision(
            action="finish",
            finish_summary="Fake provider completed investigation trajectory.",
        )


class OllamaProvider(BaseLLMProvider):
    """Local-first Ollama provider with structured JSON tool selection."""

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL or "qwen2.5:latest"

    @property
    def name(self) -> str:
        return f"ollama ({self.model})"

    @property
    def is_available(self) -> bool:
        return bool(self.base_url and self.model)

    async def decide_next_step(
        self,
        question: str,
        target_module_id: str,
        available_tools: List[Dict[str, Any]],
        investigation_history: List[Dict[str, Any]],
        remaining_budget: int,
    ) -> LLMDecision:
        tools_desc = "\n".join([f"- {t['name']}: {t.get('description', '')}" for t in available_tools])

        history_desc = json.dumps(investigation_history, indent=2)

        prompt = f"""You are the NexusAct Graph Intelligence Agent.
Your job is to investigate a software codebase graph to answer this engineering question:
"{question}"

Target entity under investigation: {target_module_id}
Remaining tool budget: {remaining_budget}

Available MCP Graph Tools:
{tools_desc}

Investigation history so far:
{history_desc}

INSTRUCTIONS:
1. Review the question, target, and what has already been investigated.
2. If more evidence is needed and budget allows, choose ONE tool from the available tools.
   - Use 'nexusact_trace_impact' to find upstream modules that depend on this target.
   - Use 'nexusact_who_knows' to identify developers who modified this module or its affected callers.
   - Use 'nexusact_page_rank' to determine structural architectural importance.
   - Use 'nexusact_simulate_remove_module' to test isolated removal blast-radius in a cloned graph.
3. If sufficient evidence has been collected to answer the question thoroughly,
   or budget is exhausted, finish and provide an explanation.
4. If the user asked to propose or create an issue, include suggested_action_title and suggested_action_body.

Respond ONLY with a JSON object matching this schema:
{{
  "action": "call_tool" | "finish",
  "tool_call": {{
    "tool_name": "nexusact_trace_impact" | "nexusact_who_knows" |
                 "nexusact_page_rank" | "nexusact_simulate_remove_module",
    "arguments": {{ ... }},
    "reasoning": "Why this specific tool is needed now"
  }} | null,

  "finish_summary": "Comprehensive evidence-based answer" | null,
  "suggested_action_title": "Issue title" | null,
  "suggested_action_body": "Issue body with graph findings" | null
}}
"""

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a graph intelligence AI agent. Always output valid JSON.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "stream": False,
                        "format": "json",
                        "options": {"temperature": 0.1},
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                content = data.get("message", {}).get("content", "{}")
                parsed = json.loads(content)
                return LLMDecision.model_validate(parsed)
        except Exception as e:
            logger.warning("Ollama call failed or produced invalid JSON: %s. Falling back to finished status.", e)
            return LLMDecision(
                action="finish",
                finish_summary=f"Investigation concluded (Ollama model call limitation: {e}).",
            )


class GeminiProvider(BaseLLMProvider):
    """Google Gemini Developer API provider for structured, bounded tool planning."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL or "gemini-2.5-flash"
        self._client: Any = None
        if self.api_key:
            try:
                from google import genai

                self._client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning("Failed to initialize Google GenAI client: %s", e)

    @property
    def name(self) -> str:
        return f"gemini ({self.model})"

    @property
    def is_available(self) -> bool:
        return bool(self.api_key and self._client is not None)

    async def decide_next_step(
        self,
        question: str,
        target_module_id: str,
        available_tools: List[Dict[str, Any]],
        investigation_history: List[Dict[str, Any]],
        remaining_budget: int,
    ) -> LLMDecision:
        if not self.is_available:
            return LLMDecision(
                action="finish",
                finish_summary="Gemini API is not configured or unavailable.",
            )

        tools_desc = "\n".join([f"- {t['name']}: {t.get('description', '')}" for t in available_tools])
        history_desc = json.dumps(investigation_history, indent=2)

        prompt = f"""You are the NexusAct Graph Intelligence Agent Planner.
Your job is to select the most appropriate graph tool to investigate this engineering question:
"{question}"

Target entity under investigation: {target_module_id}
Remaining tool budget: {remaining_budget}

Available MCP Graph Tools:
{tools_desc}

Investigation history so far:
{history_desc}

INSTRUCTIONS:
1. Examine the question, target, and what has already been investigated.
2. If more evidence is needed and budget allows, choose ONE tool from the available tools list:
   - For impact or break questions: use 'nexusact_trace_impact'
   - For contributor/ownership questions: use 'nexusact_who_knows'
   - For relationship paths between two components: use 'nexusact_shortest_path'
   - For immediate caller/callee connections: use 'nexusact_graph_neighborhood'
   - For centrality/architectural rank: use 'nexusact_page_rank'
   - For isolated counterfactual simulation: use 'nexusact_simulate_remove_module'
   - For dependency vulnerability triage: use 'nexusact_security_triage'
   - For suspicious fraud pattern investigation: use 'nexusact_investigate_fraud'
3. If sufficient evidence has been collected to answer the question thoroughly, or budget is 0, choose action 'finish'.
4. Include suggested_action_title and suggested_action_body if an action proposal is relevant.

Respond ONLY with a JSON object matching this schema:
{{
  "action": "call_tool" | "finish",
  "tool_call": {{
    "tool_name": "<name from available tools>",
    "arguments": {{ ... }},
    "reasoning": "<concise explanation for selecting this tool>"
  }} | null,
  "finish_summary": "<concise summary of findings>" | null,
  "suggested_action_title": "<action title>" | null,
  "suggested_action_body": "<action markdown body>" | null
}}
"""
        try:
            from google.genai import types

            response = self._client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
            raw_text = response.text or "{}"
            parsed = json.loads(raw_text)
            return LLMDecision.model_validate(parsed)
        except Exception as e:
            logger.warning("Gemini model call failed or returned invalid output: %s. Concluding step.", e)
            return LLMDecision(
                action="finish",
                finish_summary=f"Investigation concluded (Gemini provider notice: {e}).",
            )


def get_llm_provider() -> BaseLLMProvider:
    """Returns the configured LLM provider according to environment settings."""
    provider_type = settings.LLM_PROVIDER.lower().strip()

    if provider_type == "gemini":
        gemini = GeminiProvider()
        if gemini.is_available:
            return gemini
        return NoneLLMProvider()
    elif provider_type == "ollama":
        return OllamaProvider()
    elif provider_type == "fake":
        return FakeLLMProvider()
    elif provider_type == "none":
        return NoneLLMProvider()
    else:
        return NoneLLMProvider()
