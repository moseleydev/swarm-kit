# Global State

Long workflows quickly fill the context window when every fact has to be repeated in the
chat. Swarm Kit gives agents a shared **state dictionary** instead:

- It is included as JSON in **every** agent's system prompt.
- Agents change it with the built-in `update_state(key, value)` tool.
- You read it from `result.state` after the run.

```python
result = swarm.execute(
    "Triage",
    "I'm on the enterprise plan and my SSO login is broken",
    state={"user_tier": "enterprise", "issue_category": None, "resolved": False},
)
print(result.state)
# {'user_tier': 'enterprise', 'issue_category': 'sso', 'resolved': False}
```

## Tips

- **Seed the keys you care about.** Agents are much more likely to fill in `issue_category`
  if it is already in the state with a `None` value.
- **Mention the state in instructions**, for example: *"Record the order number in the state
  as `order_id`."*
- The `update_state` tool accepts JSON-encoded strings and decodes them before storing the value.
  Numbers, booleans, lists, objects and `null` become their corresponding Python types.
  Plain text that is not valid JSON is kept unchanged, including `NaN`, `Infinity` and `-Infinity`.
  To preserve numeric-looking text as a string,
  send a quoted JSON string: `value='"42"'` stores `"42"`, whereas `value="42"` stores `42`.
  Native JSON values returned by a provider are preserved as well.
- The dictionary you pass in is updated in place and also returned as `result.state`.
- Your own tools can read or write the same dictionary if they have a reference to it.

!!! note
    State is visible to every agent and is sent to the model on every call. Don't put
    secrets in it, and keep it small.
