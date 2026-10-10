# 🐝 Swarm Agent Kit

**A minimalist, state-aware multi-agent orchestration framework for Python.**

[![PyPI version](https://img.shields.io/pypi/v/swarm-agent-kit.svg?color=blue)](https://pypi.org/project/swarm-agent-kit/)
[![CI](https://github.com/moseleydev/swarm-kit/actions/workflows/ci.yml/badge.svg)](https://github.com/moseleydev/swarm-kit/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/moseleydev/swarm-kit/blob/main/LICENSE)
[![Docs](https://img.shields.io/badge/docs-live-brightgreen)](https://moseleydev.github.io/swarm-kit/)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-orange.svg)](https://github.com/moseleydev/swarm-kit/blob/main/CONTRIBUTING.md)
[![Hacktoberfest](https://img.shields.io/badge/Hacktoberfest-friendly-ff6f00.svg)](https://github.com/moseleydev/swarm-kit/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
[![Support on FLOSS Africa](https://img.shields.io/badge/support-FLOSS%20Africa-f59e0b.svg)](https://flossafrica.com/m/moseleydev?p=swarm-kit)
[![GitHub stars](https://img.shields.io/github/stars/moseleydev/swarm-kit?style=social)](https://github.com/moseleydev/swarm-kit/stargazers)

Swarm Kit sits between simple chat scripts and heavyweight agent frameworks. It provides
shared state, tool execution, async support, database persistence hooks and a live
dashboard. The core engine is short enough to read in one sitting.

<p align="center">
  <img src="https://raw.githubusercontent.com/moseleydev/swarm-kit/main/docs/assets/studio-demo.gif" alt="Agent Studio showing a triage agent hand a refund request to a billing agent, which updates state and calls a refund tool" width="760">
  <br><sub>The Agent Studio dashboard following a run: handoff → state update → tool call → reply.</sub>
</p>

```python
from swarm_kit import Agent, Swarm

def lookup_order(order_id: str) -> str:
    """Look up the status of a customer's order."""
    return {"ORD-123": "Shipped"}.get(order_id, "Order not found")

support = Agent(name="Support", instructions="Help customers with their orders.", tools=[lookup_order])

result = Swarm(agents=[support]).execute("Support", "Where is ORD-123?")
print(result.final_output)  # e.g. "Your order ORD-123 has shipped."
```

---

## Features

- **Two orchestration modes.** In **unsupervised** mode, agents hand off to each other on
  their own. In **supervised** mode, a planner LLM runs agents through a fixed sequence.
- **Any model.** Built on [LiteLLM](https://docs.litellm.ai/docs/providers), so OpenAI,
  Anthropic, Gemini, Ollama, Azure, Bedrock and 100+ other providers work, and each agent can
  use a different one.
- **Plain-function tools.** Pass a typed Python function and the JSON schema is generated
  from its signature and docstring. Sync and `async` functions both work.
- **Human-in-the-loop.** Mark sensitive tools with `require_approval` and decide each call
  with an `approval_handler` (sync or async).
- **Global state.** Agents read and update a shared dictionary, which keeps prompts short.
- **Bring your own database.** Save/load hooks work with Redis, Postgres, SQLite and others.
  Concurrent sessions stay isolated.
- **Async support.** `execute_async()` is safe to call from FastAPI and other `asyncio` servers.
- **Observability.** You get a live terminal transcript, a structured `event_handler`
  callback, a JSONL event log, and the **Agent Studio** dashboard.

## Installation

```bash
pip install swarm-agent-kit
```

Put your API key in a `.env` file. It is loaded automatically:

```env
OPENAI_API_KEY="sk-..."
```

Or run `swarm-kit init my-project` to generate a starter project.

## Unsupervised mode: agents hand off to each other

```python
from swarm_kit import Agent, Swarm

def process_refund(order_number: str) -> str:
    """Process a refund. Call this only once you have the order number."""
    return f"Refund issued for {order_number}."

triage = Agent(
    name="Triage",
    description="Front desk that routes customers.",
    instructions="Find out what the user needs. Refunds go to 'Billing'.",
)
billing = Agent(
    name="Billing",
    description="Handles refunds.",
    instructions="Issue refunds with process_refund, then confirm to the user.",
    tools=[process_refund],
    model="gpt-4o-mini",
)

swarm = Swarm(agents=[triage, billing])
result = swarm.execute("Triage", "I want a refund for INV-992")

print(result.last_agent, result.final_output, result.state)
```

## Supervised mode: a planner runs the agents in order

```python
swarm = Swarm(agents=[researcher, copywriter, editor])
result = swarm.execute_plan("Write a tweet about the Apollo 11 landing")

print(result.plan)          # [{'agent_name': 'Researcher', 'task': ...}, ...]
print(result.final_output)
```

## Async and database persistence

```python
async def load(session_id):
    data = await redis.get(session_id)
    return (json.loads(data)["history"], json.loads(data)["state"]) if data else ([], {})

async def save(session_id, history, state):
    await redis.set(session_id, json.dumps({"history": history, "state": state}))

swarm = Swarm(agents=[support], load_handler=load, save_handler=save, verbose=False, log_file=None)

@app.post("/chat")
async def chat(req: ChatRequest):
    result = await swarm.execute_async("Support", req.message, session_id=req.user_id)
    return {"reply": result.final_output}
```

## Agent Studio

```bash
swarm-kit studio   # http://127.0.0.1:8000
```

The Studio is a live, local dashboard that shows each response, handoff, tool call and state
change while your swarm runs.

## Documentation

The full guides and API reference are at **[moseleydev.github.io/swarm-kit](https://moseleydev.github.io/swarm-kit/)**:

- [Getting Started](https://moseleydev.github.io/swarm-kit/getting-started/)
- [Tools](https://moseleydev.github.io/swarm-kit/guide/tools/)
- [Execution Modes](https://moseleydev.github.io/swarm-kit/guide/modes/)
- [Persistence](https://moseleydev.github.io/swarm-kit/guide/persistence/)
- [API Reference](https://moseleydev.github.io/swarm-kit/api/)

Runnable examples are in [`examples/`](https://github.com/moseleydev/swarm-kit/tree/main/examples).

## Contributing

Contributions of any size are welcome, from typo fixes to new features, and first-time
contributors are encouraged. 🎃 **Hacktoberfest participants welcome!**

1. Pick an open issue labelled
   [`good first issue`](https://github.com/moseleydev/swarm-kit/labels/good%20first%20issue) or
   [`help wanted`](https://github.com/moseleydev/swarm-kit/labels/help%20wanted).
   Ideas include streaming, retries, token and cost tracking, persistence adapters, Studio
   improvements and new examples.
2. Comment on it to get it assigned to you, so nobody duplicates your work.
3. Follow [CONTRIBUTING.md](https://github.com/moseleydev/swarm-kit/blob/main/CONTRIBUTING.md) and open a PR.

```bash
git clone https://github.com/moseleydev/swarm-kit && cd swarm-kit
uv sync --group dev && uv run pytest   # no API key needed
```

Thanks to everyone who has contributed:

<a href="https://github.com/moseleydev/swarm-kit/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=moseleydev/swarm-kit" alt="Contributors" />
</a>

Please read our [Code of Conduct](https://github.com/moseleydev/swarm-kit/blob/main/CODE_OF_CONDUCT.md). To report a vulnerability, see
[SECURITY.md](https://github.com/moseleydev/swarm-kit/blob/main/SECURITY.md).

## Support the project

If Swarm Kit is useful to you:

- ⭐ **Star the repo**. It helps other developers find it.
- 💛 **Support development** on [FLOSS Africa](https://flossafrica.com/m/moseleydev?p=swarm-kit).

## License

[MIT](https://github.com/moseleydev/swarm-kit/blob/main/LICENSE) © moseleydev
