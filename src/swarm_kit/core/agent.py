import json
import uuid
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, Union

from litellm import acompletion, completion

from .tools import normalize_tool
from .types import AgentOutput, ToolCall

ToolSpec = Union[Callable[..., Any], Tuple[Dict[str, Any], Callable[..., Any]]]

TRANSFER_TOOL = "transfer"
UPDATE_STATE_TOOL = "update_state"
RESERVED_TOOL_NAMES = {TRANSFER_TOOL, UPDATE_STATE_TOOL}


def _normalize_require_approval(value: Any) -> set:
    """Accept a single tool name, or a collection of names. ``None`` means none."""
    if value is None:
        return set()
    if isinstance(value, str):
        return {value}
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        return set(value)
    raise TypeError(
        "require_approval must be a tool name (str) or a collection of tool names "
        f"(list, set, or tuple), not {type(value).__name__}."
    )


class Agent:
    """A single LLM-backed worker with its own instructions, model and tools.

    Args:
        name: Unique name used for routing and transfers.
        instructions: The system prompt for this agent.
        model: Any LiteLLM model string, e.g. ``"gpt-4o"`` or ``"anthropic/claude-sonnet-4-5"``.
        tools: Functions the agent may call. Each item is either a plain function
            (its schema is generated from type hints and the docstring) or a
            ``(schema, function)`` tuple. Functions may be sync or ``async``.
        api_key: Optional API key passed straight to LiteLLM.
        description: Short summary shown to the supervisor/planner and to other
            agents deciding whom to transfer to. Defaults to ``instructions``.
        model_kwargs: Extra keyword arguments forwarded to LiteLLM on every call
            (e.g. ``{"temperature": 0.2, "api_base": "..."}``).
        require_approval: A tool name, or a collection of names, that must be
            approved by the swarm's ``approval_handler`` before they run. A plain
            string is one name. The swarm raises ``ValueError`` at construction if
            this is non-empty and no handler is set, or if a name is not one of
            this agent's tools. Other non-collection types raise ``TypeError``.
    """

    def __init__(
        self,
        name: str,
        instructions: str,
        model: str = "gpt-4o",
        tools: Optional[List[ToolSpec]] = None,
        api_key: Optional[str] = None,
        description: Optional[str] = None,
        model_kwargs: Optional[Dict[str, Any]] = None,
        require_approval: Optional[Union[str, Iterable[str]]] = None,
    ):
        self.name = name
        self.instructions = instructions
        self.model = model
        self.api_key = api_key
        self.description = description or instructions
        self.model_kwargs = dict(model_kwargs or {})
        self.require_approval = _normalize_require_approval(require_approval)

        normalized = [normalize_tool(t) for t in tools or []]
        self.custom_tool_schemas = [schema for schema, _ in normalized]
        self.functions: Dict[str, Callable[..., Any]] = {}
        for schema, func in normalized:
            tool_name = schema["function"]["name"]
            if tool_name in RESERVED_TOOL_NAMES:
                raise ValueError(f"Tool name '{tool_name}' is reserved by Swarm Kit.")
            if tool_name in self.functions:
                raise ValueError(f"Duplicate tool name '{tool_name}' on agent '{name}'.")
            self.functions[tool_name] = func

        self.base_tools = [{
            "type": "function",
            "function": {
                "name": TRANSFER_TOOL,
                "description": "Transfer control to another agent.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "next_agent": {"type": "string", "description": "The name of the agent to transfer to."}
                    },
                    "required": ["next_agent"]
                }
            }
        }]

    def __repr__(self) -> str:
        return f"Agent(name={self.name!r}, model={self.model!r}, tools={list(self.functions)})"

    def _build_kwargs(
        self,
        messages: List[Dict[str, Any]],
        state: Optional[Dict[str, Any]],
        peers: Optional[Dict[str, str]] = None,
        allow_transfer: bool = True,
    ) -> Dict[str, Any]:
        """Helper to build the LiteLLM payload for both sync and async methods."""
        system_content = self.instructions
        current_tools = (self.base_tools.copy() if allow_transfer else []) + self.custom_tool_schemas

        if allow_transfer and peers:
            roster = "\n".join(f"- {name}: {desc}" for name, desc in peers.items() if name != self.name)
            if roster:
                system_content += f"\n\n--- AGENTS YOU CAN TRANSFER TO ---\n{roster}"

        if state is not None:
            system_content += f"\n\n--- CURRENT GLOBAL STATE ---\n{json.dumps(state, indent=2, default=str)}"
            current_tools.append({
                "type": "function",
                "function": {
                    "name": UPDATE_STATE_TOOL,
                    "description": "Update a value in the global state dictionary.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "string"},
                            "value": {
                                "type": "string",
                                "description": (
                                    "Value encoded as JSON, e.g. 3, false or [1, 2]. "
                                    "Plain text is kept as a string. "
                                    'Use a JSON string such as "123" to preserve numeric-looking text.'
                                ),
                            }
                        },
                        "required": ["key", "value"]
                    }
                }
            })

        kwargs: Dict[str, Any] = {
            **self.model_kwargs,
            "model": self.model,
            "messages": [{"role": "system", "content": system_content}] + messages,
        }
        if current_tools:
            kwargs["tools"] = current_tools

        if self.api_key:
            kwargs["api_key"] = self.api_key

        return kwargs

    def _parse_response(self, response) -> AgentOutput:
        """Helper to format the LLM output."""
        message = response.choices[0].message
        content = message.content or ""

        tool_calls = None
        if getattr(message, "tool_calls", None):
            tool_calls = []
            for tool in message.tool_calls:
                raw_args = tool.function.arguments or "{}"
                parse_error = None
                try:
                    arguments = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
                    if not isinstance(arguments, dict):
                        raise ValueError("arguments must be a JSON object")
                except (ValueError, TypeError) as e:
                    arguments, parse_error = {}, f"Invalid JSON arguments: {e}"
                tool_calls.append(ToolCall(
                    id=getattr(tool, "id", None) or f"call_{uuid.uuid4().hex[:24]}",
                    name=tool.function.name,
                    arguments=arguments,
                    parse_error=parse_error,
                ))

        return AgentOutput(
            agent_name=self.name,
            content=content,
            tool_calls=tool_calls,
            raw_response=response
        )

    def run(self, messages: List[Dict[str, Any]], state: Optional[Dict[str, Any]] = None, **kwargs) -> AgentOutput:
        """Standard synchronous execution."""
        response = completion(**self._build_kwargs(messages, state, **kwargs))
        return self._parse_response(response)

    async def run_async(self, messages: List[Dict[str, Any]], state: Optional[Dict[str, Any]] = None, **kwargs) -> AgentOutput:
        """Non-blocking asynchronous execution."""
        response = await acompletion(**self._build_kwargs(messages, state, **kwargs))
        return self._parse_response(response)
