import asyncio
import json
import threading
import time

import pytest
from conftest import make_response, tool_call

from swarm_kit import Agent, Swarm, SwarmResult


def make_swarm(**kwargs):
    triage = Agent(name="Triage", instructions="Route the user.", description="Front desk")
    billing = Agent(name="Billing", instructions="Handle refunds.", tools=[refund])
    return Swarm(agents=[triage, billing], verbose=False, **kwargs)


def refund(order_number: str) -> str:
    """Process a refund."""
    return f"Refunded {order_number}"


class ModelRoutedLLM:
    """Routes scripted responses by model so concurrent runs never share a queue."""

    def __init__(self):
        self.by_model = {}
        self.calls = []

    def queue(self, model, *responses):
        self.by_model.setdefault(model, []).extend(responses)

    def _next(self, kwargs):
        self.calls.append({**kwargs, "messages": [dict(m) for m in kwargs.get("messages", [])]})
        queue = self.by_model.get(kwargs.get("model"))
        if not queue:
            raise AssertionError(f"FakeLLM ran out of scripted responses for model {kwargs.get('model')!r}")
        return queue.pop(0)

    def completion(self, **kwargs):
        return self._next(kwargs)

    async def acompletion(self, **kwargs):
        return self._next(kwargs)


def install_llm(monkeypatch, fake):
    import swarm_kit.core.agent as agent_mod
    import swarm_kit.core.swarm as swarm_mod

    monkeypatch.setattr(agent_mod, "completion", fake.completion)
    monkeypatch.setattr(agent_mod, "acompletion", fake.acompletion)
    monkeypatch.setattr(swarm_mod, "completion", fake.completion)
    monkeypatch.setattr(swarm_mod, "acompletion", fake.acompletion)


def test_rejects_duplicate_agents_and_unknown_start_agent(llm):
    a = Agent(name="A", instructions="x")
    with pytest.raises(ValueError, match="Duplicate"):
        Swarm(agents=[a, a])
    with pytest.raises(ValueError, match="not found"):
        Swarm(agents=[a], verbose=False).execute("Nope", "hi")


def test_simple_reply_returns_result(llm):
    llm.queue(make_response("Hello!"))
    result = make_swarm().execute("Triage", "hi")
    assert isinstance(result, SwarmResult)
    assert result.final_output == "Hello!"
    assert result.last_agent == "Triage"
    assert result.history[-1] == {"role": "assistant", "content": "Hello!"}


def test_transfer_and_tool_execution_use_proper_tool_messages(llm):
    llm.queue(
        make_response(None, [tool_call("transfer", {"next_agent": "Billing"}, "t1")]),
        make_response(None, [tool_call("refund", {"order_number": "INV-9"}, "r1")]),
        make_response("Your refund is done."),
    )
    result = make_swarm().execute("Triage", "refund INV-9")

    assert result.last_agent == "Billing"
    assert result.final_output == "Your refund is done."
    tool_msgs = [m for m in result.history if m["role"] == "tool"]
    assert tool_msgs == [
        {"role": "tool", "tool_call_id": "t1", "name": "transfer", "content": "Transferred to Billing."},
        {"role": "tool", "tool_call_id": "r1", "name": "refund", "content": "Refunded INV-9"},
    ]
    # The second LLM call must be made with the Billing agent's prompt.
    assert llm.calls[1]["messages"][0]["content"].startswith("Handle refunds.")


def test_every_parallel_tool_call_gets_a_response(llm):
    llm.queue(
        make_response(None, [
            tool_call("update_state", {"key": "a", "value": "1"}, "s1"),
            tool_call("update_state", {"key": "b", "value": "2"}, "s2"),
        ]),
        make_response("done"),
    )
    result = make_swarm().execute("Triage", "go")
    assert result.state == {"a": 1, "b": 2}
    assert [m["tool_call_id"] for m in result.history if m["role"] == "tool"] == ["s1", "s2"]


def test_invalid_transfer_is_reported_back_instead_of_ending_the_run(llm):
    llm.queue(
        make_response(None, [tool_call("transfer", {"next_agent": "Ghost"})]),
        make_response("Sorry, let me help directly."),
    )
    result = make_swarm().execute("Triage", "hi")
    tool_msg = next(m for m in result.history if m["role"] == "tool")
    assert "unknown agent 'Ghost'" in tool_msg["content"]
    assert result.final_output == "Sorry, let me help directly."


def test_tool_exceptions_and_unknown_tools_are_fed_back(llm):
    def boom() -> str:
        """Explodes."""
        raise RuntimeError("kaput")

    agent = Agent(name="A", instructions="x", tools=[boom])
    llm.queue(
        make_response(None, [tool_call("boom", {}, "b1"), tool_call("missing", {}, "m1")]),
        make_response("ok"),
    )
    result = Swarm(agents=[agent], verbose=False).execute("A", "go")
    contents = [m["content"] for m in result.history if m["role"] == "tool"]
    assert "RuntimeError: kaput" in contents[0]
    assert "not available" in contents[1]


def test_max_turns_is_respected(llm):
    llm.queue(*[make_response(None, [tool_call("update_state", {"key": "k", "value": "v"}, f"c{i}")]) for i in range(3)])
    result = make_swarm().execute("Triage", "loop", max_turns=3)
    assert result.turns == 3
    assert len(llm.calls) == 3


def test_in_memory_history_persists_between_sync_calls(llm):
    swarm = make_swarm()
    llm.queue(make_response("first"), make_response("second"))
    swarm.execute("Triage", "one")
    swarm.execute("Triage", "two")
    assert [m["content"] for m in swarm.history if m["role"] == "user"] == ["one", "two"]
    swarm.reset()
    assert swarm.history == []


def test_log_file_and_event_handler(llm, tmp_path):
    events = []
    llm.queue(make_response("hi"))
    log = tmp_path / "run.jsonl"
    make_swarm(log_file=str(log), event_handler=events.append).execute("Triage", "hello")
    lines = [json.loads(line) for line in log.read_text().splitlines()]
    assert [e["action"] for e in lines] == ["Start", "Response", "Complete"]
    assert [e["action"] for e in events] == ["Start", "Response", "Complete"]


def test_rich_markup_in_model_output_does_not_crash(llm):
    swarm = make_swarm()
    swarm.verbose = True
    llm.queue(make_response("weird [/bold] text [red]"))
    assert swarm.execute("Triage", "hi").final_output == "weird [/bold] text [red]"


async def test_async_sessions_are_isolated_and_persisted(llm):
    db = {}

    async def save(session_id, history, state):
        db[session_id] = (list(history), dict(state))

    def load(session_id):
        return db.get(session_id, ([], {}))

    swarm = make_swarm(save_handler=save, load_handler=load)
    llm.queue(make_response("for alice"), make_response("for bob"), make_response("alice again"))

    await swarm.execute_async("Triage", "I am Alice", session_id="alice")
    await swarm.execute_async("Triage", "I am Bob", session_id="bob")
    # Bob must never see Alice's history.
    assert all("Alice" not in str(m.get("content")) for m in llm.calls[1]["messages"])

    result = await swarm.execute_async("Triage", "Me again", session_id="alice")
    assert [m["content"] for m in result.history if m["role"] == "user"] == ["I am Alice", "Me again"]
    assert len(db["alice"][0]) == 4


@pytest.mark.parametrize("run_sync_tools_in_thread", [False, True])
async def test_async_tools_are_awaited(llm, run_sync_tools_in_thread):
    tool_thread = []

    async def fetch(url: str) -> dict:
        """Fetch a URL."""
        tool_thread.append(threading.get_ident())
        return {"status": 200, "url": url}

    agent = Agent(name="A", instructions="x", tools=[fetch])
    llm.queue(make_response(None, [tool_call("fetch", {"url": "x"}, "f1")]), make_response("ok"))
    result = await Swarm(
        agents=[agent], verbose=False, run_sync_tools_in_thread=run_sync_tools_in_thread
    ).execute_async("A", "go")
    tool_msg = next(m for m in result.history if m["role"] == "tool")
    assert json.loads(tool_msg["content"]) == {"status": 200, "url": "x"}
    # A genuine async tool is awaited on the current event loop, never offloaded to a thread.
    assert tool_thread == [threading.get_ident()]


async def test_blocking_sync_tools_from_concurrent_runs_overlap(monkeypatch):
    both_in_flight = threading.Barrier(2, timeout=5)

    def blocking(tag: str) -> str:
        """Return only once another run's tool is in flight at the same time."""
        both_in_flight.wait()
        # The barrier is the real oracle; this sleep makes the overlap literal too:
        # both runs are inside their blocking tool at the same time.
        time.sleep(0.05)
        return f"{tag}-done"

    triage = Agent(name="Triage", instructions="x", model="model-triage", tools=[blocking])
    billing = Agent(name="Billing", instructions="y", model="model-billing", tools=[blocking])
    swarm = Swarm(
        agents=[triage, billing],
        verbose=False,
        log_file=None,
        run_sync_tools_in_thread=True,
    )

    # Route independently by model: the two concurrent runs never share a response queue.
    routed = ModelRoutedLLM()
    routed.queue(
        "model-triage",
        make_response(None, [tool_call("blocking", {"tag": "triage"}, "t1")]),
        make_response("triage finished"),
    )
    routed.queue(
        "model-billing",
        make_response(None, [tool_call("blocking", {"tag": "billing"}, "b1")]),
        make_response("billing finished"),
    )
    install_llm(monkeypatch, routed)

    triage_result, billing_result = await asyncio.gather(
        swarm.execute_async("Triage", "go", history=[]),
        swarm.execute_async("Billing", "go", history=[]),
    )

    # The barrier only releases when both blocking tools are in flight simultaneously.
    assert not both_in_flight.broken
    assert triage_result.final_output == "triage finished"
    assert billing_result.final_output == "billing finished"
    assert [m["content"] for m in triage_result.history if m["role"] == "tool"] == ["triage-done"]
    assert [m["content"] for m in billing_result.history if m["role"] == "tool"] == ["billing-done"]


def test_async_tool_works_from_sync_execute(llm):
    async def ping() -> str:
        """Ping."""
        return "pong"

    agent = Agent(name="A", instructions="x", tools=[ping])
    llm.queue(make_response(None, [tool_call("ping", {}, "p1")]), make_response("ok"))
    result = Swarm(agents=[agent], verbose=False).execute("A", "go")
    assert any(m.get("content") == "pong" for m in result.history)


# ------------------------------------------------------------------
# Supervised mode
# ------------------------------------------------------------------
def plan_response(steps):
    return make_response(json.dumps({"plan": steps}))


def test_execute_plan_runs_steps_in_order_without_transfer_tool(llm):
    llm.queue(
        plan_response([
            {"agent_name": "Triage", "task": "classify"},
            {"agent_name": "Ghost", "task": "ignored"},
            {"agent_name": "Billing", "task": "refund"},
        ]),
        make_response(None, [tool_call("update_state", {"key": "category", "value": "refund"}, "s1")]),
        make_response("classified"),
        make_response("refunded"),
    )
    result = make_swarm().execute_plan("I need a refund", state={"user": "u1"})

    assert [s["agent_name"] for s in result.plan] == ["Triage", "Billing"]
    assert result.state == {"user": "u1", "category": "refund"}
    assert result.final_output == "refunded"
    for call in llm.calls[1:]:
        assert "transfer" not in [t["function"]["name"] for t in call["tools"]]


def test_plan_parsing_tolerates_code_fences(llm):
    llm.queue(make_response('Sure!\n```json\n{"plan": [{"agent_name": "Triage", "task": "t"}]}\n```'), make_response("ok"))
    result = make_swarm().execute_plan("x")
    assert result.plan == [{"agent_name": "Triage", "task": "t"}]


def test_invalid_plan_raises(llm):
    llm.queue(make_response("no json here"))
    with pytest.raises(ValueError, match="valid JSON"):
        make_swarm().execute_plan("x")


async def test_execute_plan_async_uses_async_planner_and_saves(llm):
    saved = {}
    swarm = make_swarm(save_handler=lambda sid, h, s: saved.update({sid: s}))
    llm.queue(plan_response([{"agent_name": "Billing", "task": "refund"}]), make_response("done"))
    result = await swarm.execute_plan_async("refund", session_id="job1")
    assert result.final_output == "done"
    assert "job1" in saved

def test_tracks_token_usage_and_response_events(llm, tmp_path):
    events = []
    log = tmp_path / "run.jsonl"
    swarm = make_swarm(log_file=str(log), event_handler=events.append)

    # Queue two turns with token usage
    llm.queue(
        make_response("First answer", usage={"prompt_tokens": 20, "completion_tokens": 10}),
        make_response("Second answer", usage={"prompt_tokens": 15, "completion_tokens": 5}),
    )

    result1 = swarm.execute("Triage", "Query 1")
    assert result1.usage.prompt_tokens == 20
    assert result1.usage.completion_tokens == 10

    result2 = swarm.execute("Triage", "Query 2")
    assert result2.usage.prompt_tokens == 15
    assert result2.usage.completion_tokens == 5

    # Verify per-call usage on Response event
    response_events = [e for e in events if e["action"] == "Response"]
    assert len(response_events) == 2
    assert response_events[0]["usage"]["prompt_tokens"] == 20
    assert response_events[0]["usage"]["completion_tokens"] == 10
    assert response_events[1]["usage"]["prompt_tokens"] == 15
    assert response_events[1]["usage"]["completion_tokens"] == 5

def test_token_usage_accumulates_across_tool_calls(llm):
    events = []
    swarm = make_swarm(event_handler=events.append)

    # Turn 1: Agent calls a tool silently (no text)
    # Turn 2: Agent replies with final text
    llm.queue(
        make_response(
            None,
            [tool_call("update_state", {"key": "x", "value": "1"}, "t1")],
            usage={"prompt_tokens": 10, "completion_tokens": 5}
        ),
        make_response("Final text", usage={"prompt_tokens": 20, "completion_tokens": 10}),
    )

    result = swarm.execute("Triage", "do it")

    # The SwarmResult should have the combined total of both turns
    assert result.usage.prompt_tokens == 30
    assert result.usage.completion_tokens == 15

    # Verify the silent tool call still emitted a Response event with its tokens
    responses = [e for e in events if e["action"] == "Response"]
    assert len(responses) == 2
    assert responses[0]["content"] == ""
    assert responses[0]["usage"]["prompt_tokens"] == 10
    assert responses[1]["content"] == "Final text"
    assert responses[1]["usage"]["prompt_tokens"] == 20


def test_execute_plan_includes_planner_token_usage(llm):
    swarm = make_swarm()

    # Queue the Supervisor/Planner's response, then the Agent's response
    llm.queue(
        make_response(
            json.dumps({"plan": [{"agent_name": "Triage", "task": "help"}]}),
            usage={"prompt_tokens": 100, "completion_tokens": 50}
        ),
        make_response("Task done", usage={"prompt_tokens": 10, "completion_tokens": 5})
    )

    result = swarm.execute_plan("I need help")

    # The SwarmResult should combine the Planner (100/50) + the Agent (10/5)
    assert result.usage.prompt_tokens == 110
    assert result.usage.completion_tokens == 55
# -----------------------------------------------------------
# tests whether the kwargs reach the LLM call (for issue #6)
# -----------------------------------------------------------

def _find_pC(llm):
    for call in llm.calls:
        if call.get("response_format") == {"type": "json_object"}:
            return call
    raise AssertionError("Planner call was not found within specified LLM call log")

# test 1 checks whether the default planner kwargs reach the LLM
def test_default_planner_kwargs(llm):
    llm.queue(plan_response([]))
    make_swarm().execute_plan("write alphabet")
    pCall = _find_pC(llm)
    assert pCall["num_retries"] == 3
    assert pCall["timeout"] == 60

# test 2 checks whether the user specified planner kwargs reach the LLM
def test_user_specified_planner_kwargs(llm):
    llm.queue(plan_response([]))
    make_swarm(planner_kwargs={"num_retries": 6, "timeout": 100}).execute_plan("write alphabet")
    pCall = _find_pC(llm)
    assert pCall["num_retries"] == 6
    assert pCall["timeout"] == 100

# test 3 checks whether both the default and user specified planner kwargs reach the LLM
def test_planner_kwargs(llm):
    llm.queue(plan_response([]))
    make_swarm(planner_kwargs={"timeout": 100}).execute_plan("write alphabet")
    pCall = _find_pC(llm)
    assert pCall["num_retries"] == 3
    assert pCall["timeout"] == 100


# test 4 checks whether agent keys reach the LLM
def test_agent(llm):
    agent = Agent(name="Agent A", instructions="abc", num_retries=5, timeout=50)
    llm.queue(make_response("alphabet!"))
    Swarm(agents=[agent], verbose=False).execute("Agent A","action!")
    call = llm.calls[0]
    assert call["num_retries"] == 5
    assert call["timeout"] == 50

# test 5 checks whether model_kwargs overrides the agent keys in reaching the LLM
def test_model_kwargs_overrides(llm):
    agent = Agent(name="Agent B", instructions="123",num_retries=5, timeout=50, model_kwargs={"num_retries": 10, "timeout": 100})
    llm.queue(make_response("numbers!"))
    Swarm(agents=[agent], verbose=False).execute("Agent B","action!")
    call = llm.calls[0]
    assert call["num_retries"] == 10
    assert call["timeout"] == 100
