# API Reference

Everything public is importable from the top-level package:

```python
from swarm_kit import Agent, Swarm, SwarmResult, AgentOutput, ApprovalRequest, ToolCall, function_to_schema, __version__
```

## `Agent`

```python
Agent(
    name: str,
    instructions: str,
    model: str = "gpt-4o",
    tools: list[Callable | tuple[dict, Callable]] | None = None,
    api_key: str | None = None,
    description: str | None = None,
    model_kwargs: dict | None = None,
    require_approval: str | Iterable[str] | None = None,
)
```

| Method | Returns | Description |
| --- | --- | --- |
| `run(messages, state=None)` | `AgentOutput` | One synchronous LLM call. Tools are **not** executed. |
| `await run_async(messages, state=None)` | `AgentOutput` | One asynchronous LLM call. |

| Attribute | Description |
| --- | --- |
| `functions` | `dict[str, Callable]` of the agent's tools, keyed by name. |
| `custom_tool_schemas` | The JSON schemas sent to the model. |
| `require_approval` | `set[str]` of tool names that must be approved before they run. A plain `str` is treated as one name; a list, set or tuple of names is also accepted. Other non-collection types raise `TypeError`. |

Raises `ValueError` if a tool is named `transfer` or `update_state`, or if two tools have the
same name. Raises `TypeError` if `require_approval` is not a string or a collection of names.
See [Agents](guide/agents.md). A non-empty `require_approval` is validated when the
[`Swarm`](#swarm) is created.

## `Swarm`

```python
Swarm(
    agents: list[Agent],
    planner_model: str = "gpt-4o",
    save_handler: Callable[[str, list, dict], Any] | None = None,
    load_handler: Callable[[str], tuple[list, dict]] | None = None,
    log_file: str | None = ".swarm_runs.jsonl",
    verbose: bool = True,
    event_handler: Callable[[dict], Any] | None = None,
    planner_kwargs: dict | None = None,
    run_sync_tools_in_thread: bool = False,
    approval_handler: Callable[[ApprovalRequest], Any] | None = None,
)
```

Raises `ValueError` if `agents` is empty or contains duplicate names, if any agent has a
non-empty `require_approval` and `approval_handler` is missing, or if `require_approval`
names a tool that agent does not have.

| Argument | Description |
| --- | --- |
| `run_sync_tools_in_thread` | Opt-in (default `False`). When `True`, synchronous custom tools run via `asyncio.to_thread(...)` during `execute_async()` / `execute_plan_async()`, so they no longer block the event loop. `async def` tools are still awaited on the event loop. Cancelling a run does not kill a tool already running in its worker thread. |
| `approval_handler` | Called with an [`ApprovalRequest`](#approvalrequest) before a gated tool runs. Return `True` to run it, `False` to reject, or a string reason. May be sync or async. See [Tools](guide/tools.md#human-in-the-loop-approval). |

### Unsupervised

```python
swarm.execute(start_agent_name, user_input, state=None, max_turns=15, session_id=None, history=None) -> SwarmResult
await swarm.execute_async(start_agent_name, user_input, state=None, session_id=None, max_turns=15, history=None) -> SwarmResult
```

### Supervised

```python
swarm.execute_plan(user_input, state=None, session_id=None, history=None, max_steps_per_task=3) -> SwarmResult
await swarm.execute_plan_async(user_input, state=None, session_id=None, history=None, max_steps_per_task=3) -> SwarmResult
```

| Argument | Description |
| --- | --- |
| `start_agent_name` | First agent to run. Raises `ValueError` if unknown. |
| `user_input` | The user's message for this run. |
| `state` | Initial global state. Updated in place. |
| `session_id` | Turns on `load_handler`/`save_handler` for this run. |
| `history` | Explicit history to continue from. Copied, not mutated. |
| `max_turns` | Maximum LLM calls in unsupervised mode. |
| `max_steps_per_task` | Maximum LLM calls per plan step in supervised mode. |

### Other members

| Member | Description |
| --- | --- |
| `swarm.history` | In-memory history used when neither `history` nor a session is given. |
| `swarm.reset()` | Clears `swarm.history`. |
| `swarm.agent_registry` | `dict[str, Agent]`. |

## `SwarmResult`

A Pydantic model returned by every `execute*` method.

| Field | Type | Description |
| --- | --- | --- |
| `history` | `list[dict]` | Full message history after the run. |
| `state` | `dict` | Final global state. |
| `final_output` | `str \| None` | The last text an agent replied with. |
| `last_agent` | `str \| None` | Name of the agent that ran last. |
| `turns` | `int` | Number of LLM calls made by agents. |
| `plan` | `list[dict] \| None` | Validated plan (supervised mode only). |
| `session_id` | `str \| None` | The session ID, if one was given. |

## `AgentOutput`

| Field | Type | Description |
| --- | --- | --- |
| `agent_name` | `str` | |
| `content` | `str` | Text reply (may be empty). |
| `tool_calls` | `list[ToolCall] \| None` | Tool calls requested by the model. |
| `raw_response` | `Any` | The raw LiteLLM response, for debugging. |

`to_message()` turns it into an OpenAI-style assistant message dict.

## `ToolCall`

| Field | Type | Description |
| --- | --- | --- |
| `id` | `str` | Provider tool-call ID. |
| `name` | `str` | Tool name. |
| `arguments` | `dict` | Parsed arguments. |
| `parse_error` | `str \| None` | Set when the model sent invalid JSON. |

## `ApprovalRequest`

A dataclass passed to `approval_handler` for each gated tool call. `arguments` is a deep
copy of the model's arguments; mutating it does not change what the tool runs with.

| Field | Type | Description |
| --- | --- | --- |
| `agent_name` | `str` | Agent that requested the call. |
| `tool_name` | `str` | Tool name. |
| `arguments` | `dict` | Deep copy of the parsed arguments. |
| `call_id` | `str` | Provider tool-call ID. Changes if a run is retried; do not use it as an idempotency key. |
| `session_id` | `str \| None` | The run's session ID, if one was given. |

## `function_to_schema(func) -> dict`

Builds an OpenAI-style tool schema from a function's signature, type hints and docstring.
See [Tools](guide/tools.md).

## CLI

| Command | Description |
| --- | --- |
| `swarm-kit init [DIR] [--force]` | Creates `DIR/agents/main.py` and `DIR/.env.example`. |
| `swarm-kit studio [--host 127.0.0.1] [--port 8000] [--log-file .swarm_runs.jsonl]` | Starts the Agent Studio dashboard. |
| `swarm-kit version` | Prints the installed version. |
