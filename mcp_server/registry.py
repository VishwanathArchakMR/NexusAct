"""Registry for NexusAct MCP tools with versioning and safety classification."""

from typing import Any, Callable, Dict, NamedTuple

from mcp_server.schemas import ToolClassification


class ToolDefinition(NamedTuple):
    name: str
    version: str
    description: str
    classification: ToolClassification
    handler: Callable[..., Any]
    input_schema: Any
    output_schema: Any


class ToolRegistry:
    """Central registry enforcing contracts and safety restrictions on MCP tools."""

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        version: str,
        description: str,
        classification: ToolClassification,
        input_schema: Any,
        output_schema: Any,
    ):
        """Decorator to register an MCP tool handler."""

        def decorator(handler: Callable[..., Any]):
            self._tools[name] = ToolDefinition(
                name=name,
                version=version,
                description=description,
                classification=classification,
                handler=handler,
                input_schema=input_schema,
                output_schema=output_schema,
            )
            return handler

        return decorator

    def get_tool(self, name: str) -> ToolDefinition:
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' is not registered.")
        return self._tools[name]

    def list_tools(self) -> Dict[str, ToolDefinition]:
        return dict(self._tools)


# Global registry singleton
tool_registry = ToolRegistry()
