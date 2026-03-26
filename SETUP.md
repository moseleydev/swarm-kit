````markdown
# Welcome to Swarm Kit 🐝

> A minimalist, state-aware multi-agent orchestration framework for Python.

Swarm Kit allows you to build fault-tolerant AI workflows with native state management, tool execution, and database persistence.

## Why Swarm Kit?

Most agent frameworks force you into a single paradigm. Swarm Kit gives you the best of both worlds:

1. **Unsupervised Mode:** Agents dynamically chat, use tools, and transfer control to each other. Perfect for customer support bots.
2. **Supervised Mode:** An LLM Supervisor generates a strict JSON execution plan and forces specialized agents to run in sequence. Perfect for data pipelines.

---

## Quick Installation

```bash
pip install swarm-kit
```
````

Set your API keys in a `.env` file (Swarm Kit uses LiteLLM under the hood, so it supports 100+ providers):

```env
OPENAI_API_KEY="sk-..."
GEMINI_API_KEY="..."
```

---

## Core Features

### 1. Database Persistence (Bring Your Own DB)

Never lose chat history. Pass your own save/load functions to the Swarm, and it will automatically handle session resumption.

```python
def save_to_redis(session_id, history, state):
    redis_client.set(session_id, {"history": history, "state": state})

swarm = Swarm(agents=[...], save_handler=save_to_redis)
await swarm.execute_async(..., session_id="ticket_123")
```

### 2. Global State Management

Instead of stuffing massive context into the chat history, agents share a `state` dictionary. They are equipped with an `update_state` tool natively to mutate this memory.

### 3. Agent Studio UI

Swarm Kit comes with a beautiful local dashboard to visualize agent handovers, tool executions, and state changes in real-time.

```bash
swarm-kit studio
```

_Runs on localhost:8000_

````

### Deploying the Documentation
Because MkDocs is installed within your `uv` environment, you must prefix your deployment command with `uv run`.

Make sure you have pushed your code to GitHub, then run this in your terminal:

```bash
uv run mkdocs gh-deploy
````
