from pydantic import BaseModel
from typing import List, Optional, Any, Dict

class AgentOutput(BaseModel):
    agent_name: str
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    raw_response: Any  # For debugging