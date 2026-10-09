import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """A single tool call requested by an agent."""

    id: str
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    # Set when the model returned arguments that were not valid JSON.
    parse_error: Optional[str] = None


class AgentOutput(BaseModel):
    """The parsed result of a single LLM call made by an agent."""

    agent_name: str
    content: str
    tool_calls: Optional[List[ToolCall]] = None
    raw_response: Any = None  # For debugging

    def to_message(self) -> Dict[str, Any]:
        """Render this output as an OpenAI-style assistant message for the history."""
        message: Dict[str, Any] = {"role": "assistant", "content": self.content or None}
        if self.tool_calls:
            message["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
                }
                for call in self.tool_calls
            ]
        return message


class SwarmResult(BaseModel):
    """Returned by every ``Swarm.execute*`` method."""

    history: List[Dict[str, Any]]
    state: Dict[str, Any]
    last_agent: Optional[str] = None
    final_output: Optional[str] = None
    turns: int = 0
    plan: Optional[List[Dict[str, Any]]] = None
    session_id: Optional[str] = None


@dataclass
class ApprovalRequest:
    """A pending tool call that needs human approval before it runs.

    ``arguments`` is a deep copy of the model's arguments. Mutating it does not
    change the values passed to the tool if the call is approved.
    """

    agent_name: str
    tool_name: str
    arguments: Dict[str, Any]
    call_id: str
    session_id: Optional[str] = None

