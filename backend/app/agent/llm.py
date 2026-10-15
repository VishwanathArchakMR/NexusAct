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


def get_llm_provider() -> BaseLLMProvider:
    """Returns the configured LLM provider according to environment settings."""
    provider_type = settings.LLM_PROVIDER.lower().strip()

    if provider_type == "ollama":
        return OllamaProvider()
    elif provider_type == "fake":
        return FakeLLMProvider()
    elif provider_type == "none":
        # Check if Ollama is accessible locally
        return NoneLLMProvider()
    else:
        return NoneLLMProvider()
