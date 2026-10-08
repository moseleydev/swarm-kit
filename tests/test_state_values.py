import json

import pytest
from conftest import make_response, tool_call

from swarm_kit import Agent, Swarm


@pytest.mark.parametrize("use_async", [False, True])
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("3", 3),
        ("42", 42),
        ('"42"', "42"),
        ("false", False),
        ("[1, 2]", [1, 2]),
        ('{"a": 1}', {"a": 1}),
        ("null", None),
        ("3.5", 3.5),
        ("hello", "hello"),
        ("NaN", "NaN"),
        ("Infinity", "Infinity"),
        ("-Infinity", "-Infinity"),
        ("00123", "00123"),
        ('"3"', "3"),
        (3, 3),
        (False, False),
        ([1, 2], [1, 2]),
    ],
)
async def test_update_state_values(llm, use_async, raw, expected):
    events = []
    state = {}
    agent = Agent(name="A", instructions="Update state.")
    swarm = Swarm(agents=[agent], verbose=False, log_file=None, event_handler=events.append)
    llm.queue(
        make_response(None, [tool_call("update_state", {"key": "value", "value": raw})]),
        make_response("done"),
    )

    if use_async:
        result = await swarm.execute_async("A", "go", state=state)
    else:
        result = swarm.execute("A", "go", state=state)

    actual = result.state["value"]
    assert actual == expected
    assert type(actual) is type(expected)
    assert state["value"] == expected

    update = next(event for event in events if event["action"] == "StateUpdate")
    assert update["value"] == expected
    assert type(update["value"]) is type(expected)

    system = llm.calls[1]["messages"][0]["content"]
    next_state = json.loads(system.split("--- CURRENT GLOBAL STATE ---\n", 1)[1])
    assert next_state["value"] == expected
    assert type(next_state["value"]) is type(expected)
