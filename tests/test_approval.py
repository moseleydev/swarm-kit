import pytest
from conftest import make_response, tool_call

from swarm_kit import Agent, ApprovalRequest, Swarm


def refund(order_number: str) -> str:
    """Process a refund."""
    return f"Refunded {order_number}"


def lookup(order_id: str) -> str:
    """Look up an order."""
    return f"found {order_id}"


def _billing(*, require_approval=None, tools=None):
    return Agent(
        name="Billing",
        instructions="Handle refunds.",
        tools=tools or [refund],
        require_approval=require_approval or {"refund"},
    )


def _swarm(agent, handler, **kwargs):
    return Swarm(agents=[agent], verbose=False, approval_handler=handler, **kwargs)


def test_sync_handler_approves(llm):
    seen = []

    def handler(req: ApprovalRequest):
        seen.append(req)
        return True

    llm.queue(make_response(None, [tool_call("refund", {"order_number": "INV-9"}, "r1")]), make_response("done"))
    result = _swarm(_billing(), handler).execute("Billing", "refund INV-9", session_id="sess-1")

    assert len(seen) == 1
    req = seen[0]
    assert (req.agent_name, req.tool_name, req.call_id, req.session_id) == ("Billing", "refund", "r1", "sess-1")
    assert req.arguments == {"order_number": "INV-9"}
    assert [m["content"] for m in result.history if m["role"] == "tool"] == ["Refunded INV-9"]


def test_sync_handler_rejects_with_false(llm):
    def handler(req):
        return False

    llm.queue(make_response(None, [tool_call("refund", {"order_number": "INV-9"}, "r1")]), make_response("ok"))
    result = _swarm(_billing(), handler).execute("Billing", "go")
    assert [m["content"] for m in result.history if m["role"] == "tool"] == ["Error: rejected by user: approval denied"]


def test_sync_handler_rejects_with_reason_string(llm):
    def handler(req):
        return "amount exceeds limit"

    llm.queue(make_response(None, [tool_call("refund", {"order_number": "INV-9"}, "r1")]), make_response("ok"))
    result = _swarm(_billing(), handler).execute("Billing", "go")
    assert [m["content"] for m in result.history if m["role"] == "tool"] == [
        "Error: rejected by user: amount exceeds limit"
    ]


def test_rejection_reason_is_in_messages_passed_to_the_model(llm):
    def handler(req):
        return "amount exceeds limit"

    llm.queue(make_response(None, [tool_call("refund", {"order_number": "INV-9"}, "r1")]), make_response("ok"))
    _swarm(_billing(), handler).execute("Billing", "go")

    tool_msgs = [m for m in llm.calls[1]["messages"] if m.get("role") == "tool"]
    assert tool_msgs == [
        {
            "role": "tool",
            "tool_call_id": "r1",
            "name": "refund",
            "content": "Error: rejected by user: amount exceeds limit",
        }
    ]


async def test_async_handler_approves(llm):
    async def handler(req):
        return True

    llm.queue(make_response(None, [tool_call("refund", {"order_number": "INV-9"}, "r1")]), make_response("ok"))
    result = await _swarm(_billing(), handler).execute_async("Billing", "go")
    assert [m["content"] for m in result.history if m["role"] == "tool"] == ["Refunded INV-9"]


async def test_async_handler_rejects(llm):
    async def handler(req):
        return False

    llm.queue(make_response(None, [tool_call("refund", {"order_number": "INV-9"}, "r1")]), make_response("ok"))
    result = await _swarm(_billing(), handler).execute_async("Billing", "go")
    assert [m["content"] for m in result.history if m["role"] == "tool"] == ["Error: rejected by user: approval denied"]


def test_handler_mutation_does_not_change_what_the_tool_runs_with(llm):
    seen = []

    def refund_with_meta(order_number: str, meta: dict) -> str:
        """Process a refund."""
        seen.append({"order_number": order_number, "meta": dict(meta)})
        return f"Refunded {order_number}/{meta['tag']}"

    def handler(req):
        req.arguments["order_number"] = "MUTATED"
        req.arguments["meta"]["tag"] = "changed"
        return True

    agent = _billing(tools=[refund_with_meta], require_approval={"refund_with_meta"})
    llm.queue(
        make_response(None, [tool_call("refund_with_meta", {"order_number": "INV-9", "meta": {"tag": "orig"}}, "r1")]),
        make_response("ok"),
    )
    result = _swarm(agent, handler).execute("Billing", "go")

    assert seen == [{"order_number": "INV-9", "meta": {"tag": "orig"}}]
    assert [m["content"] for m in result.history if m["role"] == "tool"] == ["Refunded INV-9/orig"]


def test_two_calls_in_one_turn_get_two_separate_decisions(llm):
    decisions = []

    def handler(req):
        decisions.append(req.call_id)
        return req.call_id == "r1"

    llm.queue(
        make_response(None, [
            tool_call("refund", {"order_number": "A"}, "r1"),
            tool_call("refund", {"order_number": "B"}, "r2"),
        ]),
        make_response("done"),
    )
    result = _swarm(_billing(), handler).execute("Billing", "go")

    assert decisions == ["r1", "r2"]
    assert [m["content"] for m in result.history if m["role"] == "tool"] == [
        "Refunded A",
        "Error: rejected by user: approval denied",
    ]
    tool_msgs = [m for m in llm.calls[1]["messages"] if m.get("role") == "tool"]
    assert [m["tool_call_id"] for m in tool_msgs] == ["r1", "r2"]
    assert [m["content"] for m in tool_msgs] == [
        "Refunded A",
        "Error: rejected by user: approval denied",
    ]


def test_tools_not_in_require_approval_are_not_gated(llm):
    calls = []

    def handler(req):
        calls.append(req)
        return False

    agent = Agent(name="A", instructions="x", tools=[lookup, refund], require_approval={"refund"})
    llm.queue(make_response(None, [tool_call("lookup", {"order_id": "1"}, "l1")]), make_response("ok"))
    result = _swarm(agent, handler).execute("A", "go")

    assert calls == []
    assert [m["content"] for m in result.history if m["role"] == "tool"] == ["found 1"]


def test_missing_approval_handler_raises():
    agent = _billing()
    with pytest.raises(ValueError, match="approval_handler"):
        Swarm(agents=[agent], verbose=False)


def test_unknown_require_approval_tool_raises():
    agent = Agent(
        name="Billing",
        instructions="x",
        tools=[refund],
        require_approval={"process_refnd", "delet"},
    )
    with pytest.raises(ValueError, match="process_refnd") as exc:
        Swarm(agents=[agent], verbose=False, approval_handler=lambda req: True)
    assert "delet" in str(exc.value)
    assert "Billing" in str(exc.value)


def test_require_approval_string_is_one_tool_name_and_gates(llm):
    seen = []

    def handler(req):
        seen.append(req.tool_name)
        return True

    agent = Agent(name="Billing", instructions="x", tools=[refund], require_approval="refund")
    assert agent.require_approval == {"refund"}
    llm.queue(make_response(None, [tool_call("refund", {"order_number": "INV-9"}, "r1")]), make_response("ok"))
    result = _swarm(agent, handler).execute("Billing", "go")

    assert seen == ["refund"]
    assert [m["content"] for m in result.history if m["role"] == "tool"] == ["Refunded INV-9"]


def test_require_approval_unknown_string_raises_value_error():
    agent = Agent(name="Billing", instructions="x", tools=[refund], require_approval="process_refnd")
    with pytest.raises(ValueError, match="process_refnd") as exc:
        Swarm(agents=[agent], verbose=False, approval_handler=lambda req: True)
    message = str(exc.value)
    assert "unknown tool" in message
    assert "d, e, f" not in message


@pytest.mark.parametrize("bad", [1, True, object(), b"refund"])
def test_require_approval_non_collection_types_raise_type_error(bad):
    with pytest.raises(TypeError, match=type(bad).__name__) as exc:
        Agent(name="Billing", instructions="x", tools=[refund], require_approval=bad)
    message = str(exc.value)
    assert "str" in message
    assert "list, set, or tuple" in message
