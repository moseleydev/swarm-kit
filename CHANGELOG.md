# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- `Swarm(run_sync_tools_in_thread=True)`: opt-in support for running synchronous custom tools in
  a worker thread (`asyncio.to_thread`) during `execute_async()`/`execute_plan_async()`, so
  blocking tools no longer stall the event loop and concurrent runs can have them in flight at
  the same time. `async def` tools are still awaited on the event loop.

### Changed
- `update_state` decodes JSON-encoded string values, supporting numbers, booleans,
  lists, objects and null. Non-JSON text, including `NaN`, `Infinity` and
  `-Infinity`, remains unchanged.
- Numeric-looking strings such as IDs are now stored as numbers; send them as
  JSON strings (`'"12345"'`) to keep them as text.

## [0.2.0] - 2026-10-08

### Added
- `Swarm.execute*()` now return a `SwarmResult` (history, state, final output, last agent, turns, plan).
- Plain Python functions can be passed as tools; the JSON schema is generated from type hints
  and the docstring (`function_to_schema`). The `(schema, function)` tuple form still works.
- `async def` tools and `async` save/load handlers are supported.
- `Agent(description=..., model_kwargs=...)`: short descriptions for routing/planning, and extra
  LiteLLM parameters such as `temperature` or `api_base`.
- Agents are told which peers they can transfer to.
- `Swarm(log_file=..., verbose=..., event_handler=..., planner_kwargs=...)` and `Swarm.reset()`.
- `history=` argument on every `execute*` method; `max_steps_per_task=` for plan mode.
- CLI: `swarm-kit version`, `swarm-kit init [DIR] --force`, `swarm-kit studio --host --log-file`.
- Studio shows tool calls, results, state updates, plans and timestamps, and resets on a new run.
- `from swarm_kit import Agent, Swarm` now works (exports were declared but never imported).
- Agent Studio demo GIF in the README and docs; Hacktoberfest and issue-claiming guidelines.
- Test suite (no API keys needed), CI on Python 3.10–3.13, docs deployment workflow,
  contributor guide, code of conduct, security policy, and issue/PR templates.

### Fixed
- **Session leakage:** with a `load_handler`, a new session no longer inherits the previous
  session's in-memory history. Concurrent sessions on one `Swarm` are isolated.
- Tool calls are recorded as proper assistant `tool_calls` + `tool` result messages, so
  conversations are valid for OpenAI, Anthropic and other providers.
- All parallel tool calls in a response are executed (previously only the first one).
- A transfer to an unknown agent (or to itself) is reported back to the model instead of
  silently ending the run.
- Malformed JSON tool arguments no longer crash the run.
- The async planner no longer blocks the event loop; planner output wrapped in Markdown
  code fences is parsed; invalid plan steps are reported.
- Model output containing `[brackets]` no longer crashes Rich console output.
- Studio dashboard escapes agent names and actions (XSS) and tolerates partially written log lines.
- Unknown start agent raises `ValueError` instead of printing and returning `None`.
- PyPI environment URL in the publish workflow.

### Changed
- In plan mode the `transfer` tool is no longer offered to agents, and supervisor
  instructions are sent as `user` messages for better cross-provider compatibility.
- Examples consolidated into `examples/`; generated `site/` removed from the repository.

## [0.1.5] - 2026-03-26
- Initial public releases (0.1.0 – 0.1.5).

[Unreleased]: https://github.com/moseleydev/swarm-kit/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/moseleydev/swarm-kit/compare/v0.1.5...v0.2.0
[0.1.5]: https://github.com/moseleydev/swarm-kit/releases/tag/v0.1.5
