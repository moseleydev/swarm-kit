"""Swarm Kit: a minimalist, state-aware multi-agent orchestration framework."""

from importlib.metadata import PackageNotFoundError, version

from dotenv import load_dotenv

from .core.agent import Agent
from .core.swarm import Swarm
from .core.tools import function_to_schema
from .core.types import AgentOutput, ApprovalRequest, SwarmResult, ToolCall

# Load API keys from a local .env file, as documented.
load_dotenv()

try:
    __version__ = version("swarm-agent-kit")
except PackageNotFoundError:  # pragma: no cover - running from a source checkout
    __version__ = "0.0.0"

__all__ = [
    "Agent",
    "Swarm",
    "AgentOutput",
    "ApprovalRequest",
    "SwarmResult",
    "ToolCall",
    "function_to_schema",
    "__version__",
]
