# 🐝 Swarm Agent Kit

**A minimalist, state-aware multi-agent orchestration framework designed for production backends.**

![PyPI version](https://img.shields.io/pypi/v/swarm-agent-kit.svg?color=blue)
![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Documentation](https://img.shields.io/badge/docs-live-brightgreen)

---

## Overview

Swarm Agent Kit bridges the gap between simple chat scripts and complex production environments. It provides native state management, async execution, database persistence hooks, and a real-time observability dashboard.

**Dual-Mode Orchestration** — Choose between **Unsupervised Mode** (agents dynamically route and hand off tasks autonomously) or **Supervised Mode** (a central LLM planner forces agents through a strict sequential pipeline).

**Bring-Your-Own-Database (BYOD)** — Native persistence hooks let you seamlessly save and resume sessions using Redis, PostgreSQL, or any database of your choice.

**Production-Ready Async** — Full `async/await` support, safe to deploy inside high-concurrency frameworks like FastAPI.

**Global State Management** — Agents share and mutate a global memory dictionary via built-in tools, keeping context lean and token usage low.

**Native Tool Execution** — Bind standard Python functions and JSON schemas to specific agents to trigger external APIs.

---

## Quick Start

### Installation

```bash
pip install swarm-agent-kit
```

Set your API keys in a `.env` file (powered by LiteLLM — supports 100+ providers):

```env
OPENAI_API_KEY="sk-..."
```

### Basic Usage

```python
from swarm_kit.core.agent import Agent
from swarm_kit.core.swarm import Swarm
import asyncio

# 1. Define your specialized agents
support = Agent(
    name="Support",
    instructions="You are a helpful IT support agent. Help the user fix their bug."
)

# 2. Initialize the Swarm (with optional DB hooks)
swarm = Swarm(agents=[support])

# 3. Execute asynchronously
async def main():
    await swarm.execute_async(
        start_agent_name="Support",
        user_input="My dashboard is crashing on startup.",
        session_id="ticket_123"
    )

if __name__ == "__main__":
    asyncio.run(main())
```

---

## CLI & Observability

Swarm Agent Kit ships with a built-in CLI and a real-time local dashboard to visualize agent handovers, tool executions, and state mutations.

```bash
swarm-kit studio
```

Runs locally at `http://localhost:8000`

---

## Database Persistence

Never lose session history. Pass your own save/load handlers and Swarm Kit handles the rest:

```python
def save_to_redis(session_id, history, state):
    redis_client.set(session_id, {"history": history, "state": state})

swarm = Swarm(agents=[...], save_handler=save_to_redis)
await swarm.execute_async(..., session_id="ticket_123")
```

Works with Redis, PostgreSQL, SQLite, or any storage backend.

---

## Documentation

Full API references, tutorials, and advanced integration guides:

**[moseleydev.github.io/swarm-kit](https://moseleydev.github.io/swarm-kit/)**

---

## License

MIT © moseleydev
