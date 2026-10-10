# Swarm Kit 🐝

**A minimalist, state-aware multi-agent orchestration framework for Python.**

Swarm Kit lets you build multi-agent AI workflows with native state management, tool
execution and database persistence, without the weight of larger frameworks. The whole
engine is a few hundred lines you can read in one sitting.

![Agent Studio showing a triage agent hand a refund request to a billing agent](assets/studio-demo.gif)

```bash
pip install swarm-agent-kit
```

```python
from swarm_kit import Agent, Swarm

def lookup_order(order_id: str) -> str:
    """Look up the status of an order."""
    return {"ORD-1": "Shipped"}.get(order_id, "Not found")

support = Agent(name="Support", instructions="Help customers with orders.", tools=[lookup_order])

result = Swarm(agents=[support]).execute("Support", "Where is ORD-1?")
print(result.final_output)
```

---

## Why Swarm Kit?

Most agent frameworks lock you into one paradigm. Swarm Kit gives you both:

<div class="grid cards" markdown>

- **Unsupervised mode**

    Agents chat, call tools and **hand off** control to each other. Good for support bots and
    open-ended assistants. → [Execution modes](guide/modes.md#unsupervised-mode)

- **Supervised mode**

    A planner LLM writes a JSON plan and runs specialised agents **in sequence**. Good for
    data pipelines and structured workflows. → [Execution modes](guide/modes.md#supervised-mode)

</div>

And the things you need in production:

| Feature | What it gives you |
| --- | --- |
| [**Any model**](guide/providers.md) | Powered by LiteLLM: OpenAI, Anthropic, Gemini, Ollama, Azure, Bedrock and 100+ more, mixed freely per agent. |
| [**Plain-function tools**](guide/tools.md) | Pass a typed Python function and the JSON schema is generated for you. Sync or `async`. |
| [**Human-in-the-loop**](guide/tools.md#human-in-the-loop-approval) | Gate sensitive tools behind `require_approval` and an `approval_handler`. |
| [**Global state**](guide/state.md) | Agents share and update a state dictionary instead of re-reading long transcripts. |
| [**Bring your own database**](guide/persistence.md) | Save/load hooks for Redis, Postgres, SQLite and others. Sessions stay isolated. |
| **Async-first** | `execute_async()` is safe to call from FastAPI and other async servers. |
| [**Observability**](guide/observability.md) | A live terminal transcript, a JSONL event log, an `event_handler` callback, and the **Agent Studio** dashboard. |

## Next steps

- [Getting Started](getting-started.md) takes about five minutes.
- The [Guide](guide/agents.md) explains every concept.
- The [Examples](examples.md) are runnable scripts.
- The [API Reference](api.md) lists every parameter.
