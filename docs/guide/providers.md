# Models & Providers

Swarm Kit sends every LLM call through [LiteLLM](https://docs.litellm.ai/docs/providers), so
the `model` string selects the provider:

| Provider | Example `model` | Environment variable |
| --- | --- | --- |
| OpenAI | `gpt-4o`, `gpt-4o-mini` | `OPENAI_API_KEY` |
| Anthropic | `anthropic/claude-sonnet-4-5` | `ANTHROPIC_API_KEY` |
| Google Gemini | `gemini/gemini-2.0-flash` | `GEMINI_API_KEY` |
| Groq | `groq/llama-3.3-70b-versatile` | `GROQ_API_KEY` |
| Ollama (local) | `ollama_chat/llama3.1` | none |
| Azure OpenAI | `azure/<deployment>` | `AZURE_API_KEY`, `AZURE_API_BASE`, `AZURE_API_VERSION` |

See the [LiteLLM provider list](https://docs.litellm.ai/docs/providers) for the full list.

## Mixing models

Each agent picks its own model. A common pattern is a cheap, fast model for routing and a
stronger one for the actual work:

```python
triage = Agent(name="Triage", instructions="...", model="gpt-4o-mini")
analyst = Agent(name="Analyst", instructions="...", model="anthropic/claude-sonnet-4-5")

swarm = Swarm(agents=[triage, analyst], planner_model="gpt-4o-mini")
```

## Per-agent settings

```python
Agent(
    name="Local",
    instructions="...",
    model="ollama_chat/llama3.1",
    model_kwargs={"api_base": "http://localhost:11434", "temperature": 0},
)
```

Planner settings go through `Swarm(planner_kwargs={...})`.

## Retries and timeouts for LLM calls
A single transient error consisting of `429` or `5xx` error from the provider can abort the whole run. As a result,
Swarm Kit has default retry and timeout settings which are passed to LiteLLM in order to avoid abortion of the 
whole run.

### Agent calls
`Agent` accepts `num_retries` and `timeout` directly:

```python
agent = Agent(
    name="Support",
    instructions="...",
    num_retries=3,
    timeout=60
)
```

num_retries and timeout default to None if not specified by the user meaning LiteLLM's defaults apply

### Overriding retry and timeout via `model_kwargs`

In order to override num_retries and timeout, `model_kwargs` is utilised as shown below

```python
agent = Agent(
    name="Support",
    instructions="...",
    num_retries=3,
    model_kwargs={"temperature": 0, "num_retries": 6}
)
```

In the case the same key appears in both places, the key in `model_kwargs` is given precedence

### Planner calls (in supervised mode)
Separately from the agent, the planner runs its own LLM call with separate defaults

```python
swarm = Swarm(
    agents=[...],
    planner_kwargs={"num_retries": 6, "timeout": 100}
)
```
The values input into `planner_kwargs` override the defaults in every case. Furthermore, the planner is called once per run
and its unsuccessfulness results in abortion of the whole system

| Setting       | Default |
|---------------|---------|
| `num_retries` | `3`     |
| `timeout`     | `60`    |

!!! note "Tool calling support"
    Agents need a model that supports **function/tool calling**: transfers and state updates
    depend on it. Supervised mode also asks the planner for JSON output. For models without
    JSON mode, pass `planner_kwargs={"response_format": None}`. Swarm Kit can still parse a
    plan that is wrapped in Markdown code fences.
