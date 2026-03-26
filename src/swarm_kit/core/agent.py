from litellm import completion, acompletion
from typing import List, Dict, Any, Optional, Tuple, Callable
from .types import AgentOutput
import json

class Agent:
    def __init__(
        self, 
        name: str, 
        instructions: str, 
        model: str = "gpt-4o", 
        tools: List[Tuple[Dict[str, Any], Callable]] = None,
        api_key: Optional[str] = None
    ):
        self.name = name
        self.instructions = instructions
        self.model = model
        self.api_key = api_key
        
        self.custom_tool_schemas = [t[0] for t in tools] if tools else []
        self.functions = {t[0]["function"]["name"]: t[1] for t in tools} if tools else {}

        self.base_tools = [{
            "type": "function",
            "function": {
                "name": "transfer",
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

    def _build_kwargs(self, messages: List[Dict[str, Any]], state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Helper to build the LiteLLM payload for both sync and async methods."""
        system_content = self.instructions
        current_tools = self.base_tools.copy() + self.custom_tool_schemas
        
        if state is not None:
            system_content += f"\n\n--- CURRENT GLOBAL STATE ---\n{json.dumps(state, indent=2)}"
            current_tools.append({
                "type": "function",
                "function": {
                    "name": "update_state",
                    "description": "Update a value in the global state dictionary.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "string"},
                            "value": {"type": "string"}
                        },
                        "required": ["key", "value"]
                    }
                }
            })

        kwargs = {
            "model": self.model,
            "messages": [{"role": "system", "content": system_content}] + messages,
            "tools": current_tools
        }
        
        if self.api_key:
            kwargs["api_key"] = self.api_key
            
        return kwargs

    def _parse_response(self, response) -> AgentOutput:
        """Helper to format the LLM output."""
        message = response.choices[0].message
        content = message.content or ""
        
        tool_calls = None
        if hasattr(message, 'tool_calls') and message.tool_calls:
            tool_calls = []
            for tool in message.tool_calls:
                tool_calls.append({
                    "name": tool.function.name,
                    "arguments": json.loads(tool.function.arguments)
                })
        
        return AgentOutput(
            agent_name=self.name,
            content=content,
            tool_calls=tool_calls,
            raw_response=response
        )

    def run(self, messages: List[Dict[str, Any]], state: Optional[Dict[str, Any]] = None) -> AgentOutput:
        """Standard synchronous execution."""
        kwargs = self._build_kwargs(messages, state)
        response = completion(**kwargs)
        return self._parse_response(response)

    async def run_async(self, messages: List[Dict[str, Any]], state: Optional[Dict[str, Any]] = None) -> AgentOutput:
        """Non-blocking asynchronous execution."""
        kwargs = self._build_kwargs(messages, state)
        response = await acompletion(**kwargs)
        return self._parse_response(response)