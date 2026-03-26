````markdown
<div align="center">
  <h1>🐝 Swarm Agent Kit</h1>
  <p><b>A minimalist, state-aware multi-agent orchestration framework designed for production backends.</b></p>

[![PyPI version](https://img.shields.io/pypi/v/swarm-agent-kit.svg?color=blue)](https://pypi.org/project/swarm-agent-kit/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Documentation](https://img.shields.io/badge/docs-live-brightgreen)](https://moseleydev.github.io/swarm-kit/)

</div>

---

## 📖 Overview

Swarm Agent Kit bridges the gap between simple chat scripts and complex production environments. It provides native state management, async execution, database persistence hooks, and a real-time observability dashboard.

- **Dual-Mode Orchestration:** Choose between **Unsupervised Mode** (agents dynamically route and hand off tasks autonomously) or **Supervised Mode** (a central LLM planner forces agents through a strict sequential pipeline).
- **Bring-Your-Own-Database (BYOD):** Native persistence hooks allow you to seamlessly save and resume sessions using Redis, PostgreSQL, or any database of your choice.
- **Production-Ready Async:** Full support for non-blocking `async/await` execution, making it safe to deploy inside high-concurrency web frameworks like FastAPI.
- **Global State Management:** Agents share and mutate a global memory dictionary via built-in tools, preventing context loss and keeping token usage lean during long workflows.
- **Native Tool Execution:** Easily bind standard Python functions and JSON schemas to specific agents to trigger external APIs.

---

## 🚀 Quick Start

### Installation

Install the package via PyPI:

```bash
pip install swarm-agent-kit
```
````

Set your API keys in a `.env` file (Powered by LiteLLM, supporting 100+ providers):

```env
OPENAI_API_KEY="sk-..."
```

### Basic Usage (Dynamic Routing)

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

## 💻 CLI & Observability

Swarm Agent Kit comes with a built-in command-line interface and a real-time local dashboard to visualize agent logic, tool executions, and state mutations.

```bash
# Launch the real-time observability dashboard
swarm-kit studio
```

_(Runs locally on `http://localhost:8000`)_

---

## 📚 Documentation & Examples

For full API references, tutorials, and advanced database integration guides, visit the official documentation:

👉 **[Swarm Agent Kit Official Docs](https://www.google.com/url?sa=E&source=gmail&q=https://moseleydev.github.io/swarm-kit/)**

Looking for drop-in code? Check out the `examples/` directory in our [GitHub repository](https://www.google.com/search?q=https://github.com/moseleydev/swarm-kit/tree/main/examples).

```

```
