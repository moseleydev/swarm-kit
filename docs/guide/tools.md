# Tools

Tools let agents call your code: databases, HTTP APIs, payment providers and so on.

## Plain functions (recommended)

Pass a function with type hints and a docstring. Swarm Kit generates the JSON schema for you.

```python
from typing import Literal, Optional

def search_products(query: str, category: Optional[str] = None,
                    sort: Literal["price", "rating"] = "rating", limit: int = 5) -> list:
    """Search the product catalogue and return matching items."""
    ...

agent = Agent(name="Shop", instructions="...", tools=[search_products])
```

How the schema is generated:

- **Name**: the function name.
- **Description**: the docstring. The model reads it to decide when to call the tool, so be specific.
- **Parameters**: `str`, `int`, `float`, `bool`, `list[...]`, `dict`, `Optional[...]` and
  `Literal[...]` map to their JSON schema types. Unannotated parameters are treated as strings.
- **Required**: every parameter without a default value.

To inspect the result, call `function_to_schema` yourself:

```python
from swarm_kit import function_to_schema
print(function_to_schema(search_products))
```

## Explicit schemas

To control the schema fully, for example to add per-parameter descriptions, pass a
`(schema, function)` tuple:

```python
refund_schema = {
    "type": "function",
    "function": {
        "name": "process_refund",
        "description": "Process a refund. Call ONLY after you have the order number.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_number": {"type": "string", "description": "e.g. ORD-123"}
            },
            "required": ["order_number"],
        },
    },
}

billing = Agent(name="Billing", instructions="...", tools=[(refund_schema, process_refund)])
```

You can mix both styles in one `tools` list.

## Async tools

`async def` tools are awaited:

```python
async def fetch_weather(city: str) -> dict:
    """Get the current weather for a city."""
    async with httpx.AsyncClient() as client:
        return (await client.get(f"https://api.example.com/weather/{city}")).json()
```

With `execute_async()` they run on the current event loop. With the synchronous `execute()`
they run through `asyncio.run()`, which fails when an event loop is already running. In that
case, use `execute_async()`.

!!! note
    In `execute_async()`, **synchronous** tools run directly on the event loop by default, so a
    long blocking call stalls every other task. Avoid blocking calls in them, make them `async`,
    or opt in to a worker thread (below).

### Synchronous tools on a worker thread (opt-in)

Set `run_sync_tools_in_thread=True` to run synchronous custom tools in a worker thread during
async execution:

```python
swarm = Swarm(agents=[researcher, billing], run_sync_tools_in_thread=True)
await swarm.execute_async("Researcher", "...")
```

Each synchronous tool call is executed with `asyncio.to_thread(...)`, so the event loop stays
free and several concurrent runs can have blocking tools in flight at the same time. The option
defaults to `False` (opt-in) and applies only to synchronous custom tools during
`execute_async()` / `execute_plan_async()`.

- `async def` tools are unaffected: they are still awaited on the event loop, not sent to a thread.
- Built-in tools (`transfer`, `update_state`), save/load handlers, approval handlers, event
  handlers and the planner are unaffected.
- Cancelling the async task waiting for a synchronous tool does not stop a tool already running
  in its worker thread; the tool continues until the function returns.

## Return values and errors

- A `str` return value is passed to the model unchanged. Any other value is serialized as JSON.
- If a tool **raises**, the swarm catches the exception and sends `Error: <Type>: <message>`
  back to the model so it can recover or explain. The run continues.
- If the model calls a tool that doesn't exist, or sends invalid JSON arguments, it gets an
  error message back.

!!! warning "Treat arguments as untrusted input"
    The LLM chooses the arguments. Validate them inside every tool. For destructive
    actions, use [human-in-the-loop approval](#human-in-the-loop-approval) rather than
    trusting the model to confirm with the user.

## Human-in-the-loop approval

Destructive tools such as refunds or deletes can require a human decision before they run.
List their names on the agent — a set, list or tuple of names, or a single string — and
pass an `approval_handler` to the swarm:

```python
from swarm_kit import Agent, ApprovalRequest, Swarm

def process_refund(order_number: str) -> str:
    """Process a refund. Call ONLY after you have the order number."""
    return f"Refund issued for {order_number}."

billing = Agent(
    name="Billing",
    instructions="Issue refunds, then confirm to the user.",
    tools=[process_refund],
    require_approval={"process_refund"},
)

def approve(req: ApprovalRequest):
    print(f"{req.agent_name} wants {req.tool_name}({req.arguments})")
    return input("Approve? [y/N] ").lower() == "y"

swarm = Swarm(agents=[billing], approval_handler=approve)
```

The handler may be a regular function or `async def`, like `save_handler` / `load_handler`.
It receives an [`ApprovalRequest`](../api.md#approvalrequest) and must return:

| Return | Effect | Tool result sent to the model |
| --- | --- | --- |
| `True` | Run the tool | The tool's return value |
| `False` | Reject | `Error: rejected by user: approval denied` |
| a string | Reject with that reason | `Error: rejected by user: <reason>` |

Each call is decided on its own. Two `process_refund` calls in one model turn produce two
prompts; there is no "approve all calls of this tool" shortcut. Tools not listed in
`require_approval` run as usual.

`Swarm(...)` raises `ValueError` immediately if:

- any agent has a non-empty `require_approval` and no `approval_handler` is set, or
- a name in `require_approval` is not one of that agent's tools (so a typo like
  `{"process_refnd"}` cannot silently leave the real tool ungated).

`arguments` on the request is a **deep copy**. Mutating it does not change what the tool
runs with after a `True`.

!!! warning "Idempotency keys"
    Approval does not protect against a **retried run**. If a whole run is retried after a
    timeout, an already-approved refund can go out twice. Side-effect tools (for example
    refunds) should pass the payment provider an idempotency key derived from business data
    such as the order ID, **not** `call_id` — that identifier changes on a retried run.

## Parallel tool calls

When a model requests several tools in one response, all of them run in order. Each result
is recorded as a `tool` message linked by `tool_call_id`, which is the format OpenAI,
Anthropic and other providers expect.
