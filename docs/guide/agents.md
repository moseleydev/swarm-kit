# Agents

An `Agent` combines a system prompt, a model and an optional set of tools. Each call to the
agent makes one LLM request.

```python
from swarm_kit import Agent

researcher = Agent(
    name="Researcher",
    instructions="You research topics and answer with concise bullet points.",
    description="Finds facts about a topic.",
    model="gpt-4o-mini",
    model_kwargs={"temperature": 0.2},
    tools=[search_web],
)
```

## Parameters

| Parameter | Default | Description |
| --- | --- | --- |
| `name` | *required* | Unique name, used for routing and transfers. |
| `instructions` | *required* | The agent's system prompt. |
| `model` | `"gpt-4o"` | Any [LiteLLM model string](providers.md). |
| `tools` | `None` | Functions or `(schema, function)` tuples. See [Tools](tools.md). |
| `description` | `instructions` | A short summary that other agents and the planner see. Set this whenever your instructions are long. |
| `model_kwargs` | `{}` | Extra LiteLLM parameters, such as `temperature`, `max_tokens`, `api_base` or `timeout`. |
| `api_key` | `None` | Overrides the API key from the environment for this agent. |
| `require_approval` | `set()` | Tool names that must be approved by the swarm's `approval_handler` before they run. See [Tools](tools.md#human-in-the-loop-approval). |

## What the agent sees

When the swarm runs an agent, the system prompt is built from:

1. its `instructions`;
2. in unsupervised mode, a list of the **other agents it can transfer to** and their `description`s;
3. the **current global state** as JSON.

The rest of the context is the shared conversation history, which includes earlier agents'
replies and tool results.

## Built-in tools

Every agent gets two tools in addition to its own:

| Tool | Available | Purpose |
| --- | --- | --- |
| `transfer(next_agent)` | Unsupervised mode | Hand control to another agent. |
| `update_state(key, value)` | Always | Write to the shared [global state](state.md). |

You cannot name your own tools `transfer` or `update_state`.

## Running an agent directly

An agent can be used without a swarm. This is handy for tests and simple scripts:

```python
output = researcher.run([{"role": "user", "content": "What is LiteLLM?"}])
print(output.content, output.tool_calls)

output = await researcher.run_async(messages, state={"topic": "llms"})
```

Both return an [`AgentOutput`](../api.md#agentoutput). When you call an agent directly, tool
calls are **not** executed. The `Swarm` does that.
