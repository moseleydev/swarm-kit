import asyncio
import inspect
import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple

from litellm import acompletion, completion
from rich.console import Console
from rich.markup import escape

from .agent import TRANSFER_TOOL, UPDATE_STATE_TOOL, Agent
from .types import AgentOutput, SwarmResult, ToolCall

console = Console()

History = List[Dict[str, Any]]
SaveHandler = Callable[[str, History, Dict[str, Any]], Any]
LoadHandler = Callable[[str], Any]
EventHandler = Callable[[Dict[str, Any]], Any]


def _reject_constant(name: str) -> None:
    """Reject non-standard JSON constants when decoding state values."""
    raise ValueError(name)


# ------------------------------------------------------------------
# Requests the execution engine yields to a sync or async driver.
# The engine itself is a plain generator, so the orchestration logic
# lives in exactly one place for both execution styles.
# ------------------------------------------------------------------
@dataclass
class _LLMRequest:
    agent: Agent
    history: History
    state: Dict[str, Any]
    allow_transfer: bool


@dataclass
class _ToolRequest:
    func: Callable[..., Any]
    arguments: Dict[str, Any]


@dataclass
class _HookRequest:
    func: Callable[..., Any]
    args: Tuple[Any, ...]


@dataclass
class _PlanRequest:
    user_input: str


@dataclass
class _RunContext:
    history: History
    state: Dict[str, Any]
    session_id: Optional[str]
    turns: int = 0
    last_agent: Optional[str] = None
    final_output: Optional[str] = None
    plan: Optional[List[Dict[str, Any]]] = None
    pending_transfer: Optional[str] = None
    uses_instance_history: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)


class Swarm:
    """Orchestrates a group of agents in unsupervised or supervised mode.

    Args:
        agents: The agents participating in this swarm. Names must be unique.
        planner_model: LiteLLM model used by the supervisor in plan mode.
        save_handler: ``(session_id, history, state)`` hook called after a run
            that was given a ``session_id``. May be sync or async.
        load_handler: ``(session_id) -> (history, state)`` hook called before a
            run that was given a ``session_id``. May be sync or async.
        log_file: JSONL file the Agent Studio reads. ``None`` disables it.
        verbose: Print a live transcript to the terminal.
        event_handler: Optional callback receiving every event dict
            (``{"agent", "action", "content", "timestamp", ...}``).
        planner_kwargs: Extra LiteLLM kwargs for the planner call (e.g. ``api_key``).
        run_sync_tools_in_thread: Opt in to running synchronous custom tools in a worker
            thread during async execution. ``async def`` tools are unaffected.
    """

    def __init__(
        self,
        agents: List[Agent],
        planner_model: str = "gpt-4o",
        save_handler: Optional[SaveHandler] = None,
        load_handler: Optional[LoadHandler] = None,
        log_file: Optional[str] = ".swarm_runs.jsonl",
        verbose: bool = True,
        event_handler: Optional[EventHandler] = None,
        planner_kwargs: Optional[Dict[str, Any]] = None,
        run_sync_tools_in_thread: bool = False,
    ):
        if not agents:
            raise ValueError("A Swarm needs at least one agent.")
        self.agent_registry: Dict[str, Agent] = {}
        for agent in agents:
            if agent.name in self.agent_registry:
                raise ValueError(f"Duplicate agent name '{agent.name}'.")
            self.agent_registry[agent.name] = agent

        # In-memory history used when no session_id / history is supplied.
        self.history: History = []
        self.log_file = log_file
        self.planner_model = planner_model
        self.planner_kwargs = dict(planner_kwargs or {})
        self.verbose = verbose
        self.event_handler = event_handler
        self.run_sync_tools_in_thread = run_sync_tools_in_thread

        # Database Hooks
        self.save_handler = save_handler
        self.load_handler = load_handler

    # ==========================================
    # PUBLIC API
    # ==========================================
    def execute(
        self,
        start_agent_name: str,
        user_input: str,
        state: Optional[Dict[str, Any]] = None,
        max_turns: int = 15,
        session_id: Optional[str] = None,
        history: Optional[History] = None,
    ) -> SwarmResult:
        """Unsupervised mode (sync): agents chat, call tools and hand off freely."""
        return self._drive_sync(self._run_unsupervised(start_agent_name, user_input, state, max_turns, session_id, history))

    async def execute_async(
        self,
        start_agent_name: str,
        user_input: str,
        state: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        max_turns: int = 15,
        history: Optional[History] = None,
    ) -> SwarmResult:
        """Unsupervised mode (async), with optional database persistence."""
        return await self._drive_async(self._run_unsupervised(start_agent_name, user_input, state, max_turns, session_id, history))

    def execute_plan(
        self,
        user_input: str,
        state: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        history: Optional[History] = None,
        max_steps_per_task: int = 3,
    ) -> SwarmResult:
        """Supervised mode (sync): a planner LLM sequences the agents."""
        return self._drive_sync(self._run_supervised(user_input, state, session_id, history, max_steps_per_task))

    async def execute_plan_async(
        self,
        user_input: str,
        state: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        history: Optional[History] = None,
        max_steps_per_task: int = 3,
    ) -> SwarmResult:
        """Supervised mode (async), with optional database persistence."""
        return await self._drive_async(self._run_supervised(user_input, state, session_id, history, max_steps_per_task))

    def reset(self) -> None:
        """Clear the in-memory conversation history."""
        self.history = []

    # ==========================================
    # EVENTS / LOGGING
    # ==========================================
    def _save_log(self, agent_name: str, action: str, content: str, **extra: Any) -> None:
        event = {"agent": agent_name, "action": action, "content": content, "timestamp": time.time(), **extra}
        if self.log_file:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, default=str) + "\n")
        if self.event_handler:
            self.event_handler(event)
        if self.verbose:
            self._print_event(event)

    @staticmethod
    def _print_event(event: Dict[str, Any]) -> None:
        agent, action = escape(str(event["agent"])), event["action"]
        content = escape(str(event["content"]))
        if action == "Response":
            console.print(f"[green]{agent}:[/green] {content}\n")
        elif action == "Tool":
            console.print(f"[bold magenta]⚙️ Executing Tool:[/bold magenta] {content}")
        elif action == "ToolResult":
            console.print(f"[dim]Result: {content}[/dim]\n")
        elif action == "StateUpdate":
            console.print(f"[bold cyan]💾 State Updated:[/bold cyan] {content}")
        elif action == "Transfer":
            console.print(f"[bold yellow]🔄 {content}[/bold yellow]\n")
        elif action == "Plan":
            console.print(f"\n[bold magenta]📋 Execution Plan:[/bold magenta]\n{content}\n")
        elif action == "Error":
            console.print(f"[bold red]✖ {agent}:[/bold red] {content}")
        elif action == "Complete":
            console.print(f"[bold blue]Swarm:[/bold blue] {content} 🏁")
        else:
            console.print(f"[bold blue]Swarm:[/bold blue] {content}\n")

    def _reset_log(self) -> None:
        if self.log_file and os.path.exists(self.log_file):
            os.remove(self.log_file)

    # ==========================================
    # SHARED ENGINE PIECES
    # ==========================================
    def _get_agent(self, name: str) -> Agent:
        agent = self.agent_registry.get(name)
        if agent is None:
            raise ValueError(f"Agent '{name}' not found. Available agents: {', '.join(self.agent_registry)}")
        return agent

    @property
    def _peers(self) -> Dict[str, str]:
        return {name: agent.description for name, agent in self.agent_registry.items()}

    def _begin(self, state, session_id, history) -> Generator[Any, Any, _RunContext]:
        global_state = state if state is not None else {}
        uses_instance_history = False
        if history is not None:
            run_history = list(history)
        elif session_id and self.load_handler:
            run_history = []
        else:
            run_history = self.history
            uses_instance_history = True

        # 1. LOAD FROM DATABASE
        if session_id and self.load_handler:
            loaded = yield _HookRequest(self.load_handler, (session_id,))
            loaded_history, loaded_state = loaded if loaded else (None, None)
            if loaded_history and history is None:
                run_history = list(loaded_history)
            if loaded_state:
                global_state.update(loaded_state)
            if self.verbose:
                console.print(f"[dim]Loaded session {session_id} from database.[/dim]")

        return _RunContext(
            history=run_history,
            state=global_state,
            session_id=session_id,
            uses_instance_history=uses_instance_history,
        )

    def _finish(self, ctx: _RunContext) -> Generator[Any, Any, SwarmResult]:
        if ctx.uses_instance_history:
            self.history = ctx.history

        # 2. SAVE TO DATABASE
        if ctx.session_id and self.save_handler:
            yield _HookRequest(self.save_handler, (ctx.session_id, ctx.history, ctx.state))
            if self.verbose:
                console.print(f"[dim]Saved session {ctx.session_id} to database.[/dim]")

        return SwarmResult(
            history=ctx.history,
            state=ctx.state,
            last_agent=ctx.last_agent,
            final_output=ctx.final_output,
            turns=ctx.turns,
            plan=ctx.plan,
            session_id=ctx.session_id,
        )

    def _record_output(self, ctx: _RunContext, agent: Agent, output: AgentOutput) -> None:
        ctx.turns += 1
        ctx.last_agent = agent.name
        ctx.history.append(output.to_message())
        if output.content:
            ctx.final_output = output.content
            self._save_log(agent.name, "Response", output.content)

    def _handle_builtin(self, ctx: _RunContext, agent: Agent, call: ToolCall, allow_transfer: bool) -> Optional[str]:
        """Handle built-in tools and error cases. Returns ``None`` if a user function must run."""
        if call.parse_error:
            return f"Error: {call.parse_error}"

        if call.name == UPDATE_STATE_TOOL:
            key, value = call.arguments.get("key"), call.arguments.get("value")
            if not key:
                return "Error: 'key' is required."
            if isinstance(value, str):
                try:
                    value = json.loads(value, parse_constant=_reject_constant)
                except ValueError:
                    pass
            ctx.state[key] = value
            self._save_log(agent.name, "StateUpdate", f"{key} = {value}", key=key, value=value)
            return f"State updated '{key}' to '{value}'."

        if call.name == TRANSFER_TOOL:
            target = call.arguments.get("next_agent")
            if not allow_transfer:
                return "Error: transfers are disabled in supervised (plan) mode. Complete your assigned task."
            if target == agent.name:
                return f"Error: you are already '{agent.name}'. Continue handling the request yourself."
            if target not in self.agent_registry:
                options = ", ".join(n for n in self.agent_registry if n != agent.name) or "none"
                return f"Error: unknown agent '{target}'. Available agents: {options}."
            ctx.pending_transfer = target
            return f"Transferred to {target}."

        if call.name not in agent.functions:
            return f"Error: tool '{call.name}' is not available to {agent.name}."
        return None

    def _process_tool_calls(self, ctx: _RunContext, agent: Agent, output: AgentOutput, allow_transfer: bool):
        """Answer every tool call in ``output`` (required by OpenAI-style tool calling)."""
        for call in output.tool_calls or []:
            result = self._handle_builtin(ctx, agent, call, allow_transfer)
            if result is None:
                self._save_log(agent.name, "Tool", f"{call.name}({call.arguments})", tool=call.name)
                try:
                    value = yield _ToolRequest(agent.functions[call.name], call.arguments)
                    result = value if isinstance(value, str) else json.dumps(value, default=str)
                    self._save_log(agent.name, "ToolResult", result, tool=call.name)
                except Exception as e:
                    result = f"Error: {type(e).__name__}: {e}"
                    self._save_log(agent.name, "Error", f"Tool '{call.name}' failed: {e}", tool=call.name)
            elif result.startswith("Error:"):
                self._save_log(agent.name, "Error", result, tool=call.name)
            ctx.history.append({"role": "tool", "tool_call_id": call.id, "name": call.name, "content": result})

    # ==========================================
    # MODE 1: UNSUPERVISED
    # ==========================================
    def _run_unsupervised(self, start_agent_name, user_input, state, max_turns, session_id, history):
        current_agent = self._get_agent(start_agent_name)
        ctx = yield from self._begin(state, session_id, history)

        ctx.history.append({"role": "user", "content": user_input})
        self._reset_log()
        self._save_log("System", "Start", f"User Input: {user_input}")
        if self.verbose:
            console.print(f"[bold blue]Swarm:[/bold blue] Task started with [magenta]{current_agent.name}[/magenta] (Unsupervised)\n")

        completed = False
        for _ in range(max_turns):
            output = yield _LLMRequest(current_agent, ctx.history, ctx.state, allow_transfer=True)
            self._record_output(ctx, current_agent, output)

            if not output.tool_calls:
                completed = True
                break

            yield from self._process_tool_calls(ctx, current_agent, output, allow_transfer=True)

            if ctx.pending_transfer:
                self._save_log(current_agent.name, "Transfer", f"Transferring to {ctx.pending_transfer}...", to=ctx.pending_transfer)
                current_agent = self.agent_registry[ctx.pending_transfer]
                ctx.pending_transfer = None

        if completed:
            self._save_log("System", "Complete", "Task complete.")
        else:
            self._save_log("System", "Error", f"Stopped after reaching max_turns={max_turns}.")

        return (yield from self._finish(ctx))

    # ==========================================
    # MODE 2: SUPERVISED / PLANNER
    # ==========================================
    def _planner_messages(self, user_input: str) -> History:
        agent_descriptions = "\n".join(f"- {name}: {agent.description}" for name, agent in self.agent_registry.items())
        system_prompt = (
            "You are a Master Orchestrator. Break the user's request into a sequential plan.\n"
            f"Available Agents:\n{agent_descriptions}\n"
            "Return ONLY a JSON object with a 'plan' array. Each item must have 'agent_name' and 'task'. "
            "Only use the agent names listed above."
        )
        return [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_input}]

    def _planner_kwargs(self, messages: History) -> Dict[str, Any]:
        return {
            "response_format": {"type": "json_object"},
            **self.planner_kwargs,
            "model": self.planner_model,
            "messages": messages,
        }

    @staticmethod
    def _parse_plan(raw: Optional[str]) -> List[Dict[str, Any]]:
        """Parse the planner's response, tolerating markdown fences and surrounding text."""
        if not raw:
            raise ValueError("Planner returned an empty response.")
        text = raw.strip()
        fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if fenced:
            text = fenced.group(1).strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if not match:
                raise ValueError(f"Planner did not return valid JSON: {raw[:200]}") from e
            data = json.loads(match.group(0))

        plan = data.get("plan", []) if isinstance(data, dict) else data
        if not isinstance(plan, list):
            raise ValueError("Planner JSON must contain a 'plan' array.")
        return [step for step in plan if isinstance(step, dict)]

    def _generate_plan(self, user_input: str) -> List[Dict[str, Any]]:
        """Synchronously ask the planner model for a plan."""
        response = completion(**self._planner_kwargs(self._planner_messages(user_input)))
        return self._parse_plan(response.choices[0].message.content)

    async def _generate_plan_async(self, user_input: str) -> List[Dict[str, Any]]:
        response = await acompletion(**self._planner_kwargs(self._planner_messages(user_input)))
        return self._parse_plan(response.choices[0].message.content)

    def _run_supervised(self, user_input, state, session_id, history, max_steps_per_task):
        ctx = yield from self._begin(state, session_id, history)

        ctx.history.append({"role": "user", "content": user_input})
        self._reset_log()
        self._save_log("System", "Start", f"User Input (Plan Mode): {user_input}")
        if self.verbose:
            console.print("[bold yellow]🧠 Supervisor is generating a plan...[/bold yellow]")

        try:
            raw_plan = yield _PlanRequest(user_input)
        except Exception as e:
            self._save_log("System", "Error", f"Planning failed: {e}")
            raise

        plan = []
        for step in raw_plan:
            agent_name, task = step.get("agent_name"), step.get("task")
            if agent_name in self.agent_registry and task:
                plan.append({"agent_name": agent_name, "task": str(task)})
            else:
                self._save_log("System", "Error", f"Skipping invalid plan step: {step}")
        ctx.plan = plan
        self._save_log(
            "System", "Plan",
            "\n".join(f"  {i + 1}. {s['agent_name']}: {s['task']}" for i, s in enumerate(plan)) or "(empty plan)",
            plan=plan,
        )

        for step in plan:
            current_agent = self.agent_registry[step["agent_name"]]
            if self.verbose:
                console.print(f"[bold blue]Swarm:[/bold blue] Running step with [magenta]{current_agent.name}[/magenta]")
            ctx.history.append({
                "role": "user",
                "content": f"[Supervisor → {current_agent.name}] {step['task']}\nExecute this step and update state/use tools if needed.",
            })

            for _ in range(max_steps_per_task):
                output = yield _LLMRequest(current_agent, ctx.history, ctx.state, allow_transfer=False)
                self._record_output(ctx, current_agent, output)
                if not output.tool_calls:
                    break
                yield from self._process_tool_calls(ctx, current_agent, output, allow_transfer=False)

        self._save_log("System", "Complete", f"All planned steps complete. Final State: {json.dumps(ctx.state, default=str)}")
        return (yield from self._finish(ctx))

    # ==========================================
    # DRIVERS
    # ==========================================
    def _drive_sync(self, engine: Generator) -> SwarmResult:
        to_send: Any = None
        to_throw: Optional[BaseException] = None
        while True:
            try:
                request = engine.throw(to_throw) if to_throw else engine.send(to_send)
            except StopIteration as stop:
                return stop.value
            to_send, to_throw = None, None
            try:
                if isinstance(request, _LLMRequest):
                    to_send = request.agent.run(
                        request.history, request.state, peers=self._peers, allow_transfer=request.allow_transfer
                    )
                elif isinstance(request, _ToolRequest):
                    to_send = _resolve_sync(request.func(**request.arguments))
                elif isinstance(request, _HookRequest):
                    to_send = _resolve_sync(request.func(*request.args))
                elif isinstance(request, _PlanRequest):
                    to_send = self._generate_plan(request.user_input)
            except Exception as e:
                to_throw = e

    async def _drive_async(self, engine: Generator) -> SwarmResult:
        to_send: Any = None
        to_throw: Optional[BaseException] = None
        while True:
            try:
                request = engine.throw(to_throw) if to_throw else engine.send(to_send)
            except StopIteration as stop:
                return stop.value
            to_send, to_throw = None, None
            try:
                if isinstance(request, _LLMRequest):
                    to_send = await request.agent.run_async(
                        request.history, request.state, peers=self._peers, allow_transfer=request.allow_transfer
                    )
                elif isinstance(request, _ToolRequest):
                    if self.run_sync_tools_in_thread and not inspect.iscoroutinefunction(request.func):
                        to_send = await _resolve_async(await asyncio.to_thread(request.func, **request.arguments))
                    else:
                        to_send = await _resolve_async(request.func(**request.arguments))
                elif isinstance(request, _HookRequest):
                    to_send = await _resolve_async(request.func(*request.args))
                elif isinstance(request, _PlanRequest):
                    to_send = await self._generate_plan_async(request.user_input)
            except Exception as e:
                to_throw = e


def _resolve_sync(value: Any) -> Any:
    """Run an awaitable returned by an async tool/hook from synchronous code."""
    if not inspect.isawaitable(value):
        return value
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_await(value))
    if inspect.iscoroutine(value):
        value.close()
    raise RuntimeError(
        "An async tool or handler was called from a synchronous Swarm method inside a running "
        "event loop. Use execute_async()/execute_plan_async() instead."
    )


async def _resolve_async(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def _await(value: Any) -> Any:
    return await value
