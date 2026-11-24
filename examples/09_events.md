# 09 · Events

Deck slide 18 · [Source](09_events.py) · [Streaming events](https://github.com/microsoft/copilot-sdk/blob/v2.0.1/docs/features/streaming-events.md)

Every step of the agent loop is an event. One handler prints each tool as it
starts and the answer as it streams in.

## Run it

```bash
python examples/09_events.py
```

## How it works

```python
def on_event(event):
    match event.data:
        case ToolExecutionStartData(tool_name=name):
            print(f"\n[tool] {name} started")
        case AssistantMessageDeltaData(delta_content=text):
            print(text or "", end="", flush=True)

session = await client.create_session(
    working_directory=str(repo),
    permissions={"on_request": PermissionHandler.approve_all},  # demo
    tools={"available_tools": ToolSet().add_builtin(["glob", "view"])},
    events={"streaming": True, "on_event": on_event})
```

- `create_session` registers the `events.on_event` handler before it returns,
  so the handler sees every event of the first prompt; `session.on(handler)`
  adds a handler later.
- `events.streaming` turns on the `AssistantMessageDeltaData` chunks; without
  it you get only the final message.
- The handler matches on the event's typed data: `ToolExecutionStartData`,
  `ToolExecutionCompleteData`, `AssistantUsageData` (example 15) and more.

## Output from a live run

```text
[tool] glob started

[tool] view started
`calc.py` defines one function, `add(a, b)`. It's meant to return the sum of its two arguments, but it has a bug: it returns `a - b`, so it subtracts instead. ...
```

## Try this next

- Add a `case ToolExecutionCompleteData(success=ok):` branch to print whether
  each tool call worked.
