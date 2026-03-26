# Welcome to Swarm Kit 🐝

**A minimalist, state-aware multi-agent orchestration framework for Python.**

Swarm Kit lets you build fault-tolerant AI workflows with native state management, tool execution, and database persistence — without the complexity of heavier frameworks.

---

## Why Swarm Kit?

Most agent frameworks lock you into one paradigm. Swarm Kit gives you both:

**Unsupervised Mode** — Agents dynamically chat, use tools, and transfer control to each other. Perfect for customer support bots and open-ended assistants.

**Supervised Mode** — An LLM Supervisor generates a strict JSON execution plan and forces specialized agents to run in sequence. Perfect for data pipelines and structured workflows.

---

## Quick Installation

```bash
pip install swarm-agent-kit
```

Set your API keys in a `.env` file. Swarm Kit uses LiteLLM under the hood, supporting 100+ providers out of the box:

```env
OPENAI_API_KEY="sk-..."
GEMINI_API_KEY="..."
```

---

## Core Features

### Database Persistence (Bring Your Own DB)

Never lose chat history. Pass your own `save` and `load` functions to the Swarm — it handles session resumption automatically.

```python
def save_to_redis(session_id, history, state):
    redis_client.set(session_id, {"history": history, "state": state})

swarm = Swarm(agents=[...], save_handler=save_to_redis)
await swarm.execute_async(..., session_id="ticket_123")
```

Works with Redis, PostgreSQL, SQLite, or any storage backend you prefer.

### Global State Management

Instead of bloating the chat history with repeated context, agents share a `state` dictionary. Each agent is natively equipped with an `update_state` tool to read and mutate this shared memory — keeping token usage lean across long workflows.

```python
state = {
    "user_tier": "enterprise",
    "issue_category": None,
    "resolved": False
}
```

### Agent Studio UI

Swarm Kit ships with a local dashboard to visualize agent handovers, tool executions, and state changes in real-time.

```bash
swarm-kit studio
```

Runs at `http://localhost:8000`

---

## Next Steps

- [Getting Started](getting-started.md)
- [API Reference](api/swarm.md)
- [Examples](examples/index.md)
