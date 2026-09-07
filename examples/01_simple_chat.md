# 01 · Streaming chat

📖 **Sources (SDK v1.0.13):**
[client identity](https://github.com/github/copilot-sdk/blob/v1.0.13/docs/features/client-info.md),
[streaming events](https://github.com/github/copilot-sdk/blob/v1.0.13/docs/features/streaming-events.md),
[Python session implementation](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/session.py).

Open [the runnable source](01_simple_chat.py). This example streams text,
identifies the workshop application, and waits for completion without an
unbounded hand-written idle event.

## The flow

```mermaid
sequenceDiagram
    participant App
    participant SDK
    participant Runtime as Copilot runtime
    App->>SDK: enter CopilotClient(client_info=...)
    SDK->>Runtime: server.connect + application identity
    App->>SDK: create_session(streaming=True, available_tools=[])
    App->>SDK: session.on(listener)
    App->>SDK: send_and_wait(prompt, timeout=60)
    loop Response chunks
        Runtime-->>SDK: assistant.message_delta
        SDK-->>App: listener prints delta_content
    end
    Runtime-->>SDK: assistant.message then session.idle
    SDK-->>App: final message
    App->>SDK: unsubscribe; exit session
    SDK->>Runtime: session.detach
    App->>SDK: exit owned client
```

## Code walkthrough

### 1. Identify the application

```python
async with CopilotClient(
    client_info={
        "application_name": "ghcp-sdk-examples",
        "application_version": "0.1.0",
        "integration_name": "python-workshop",
        "integration_version": "1.0.13",
    },
) as client:
    ...
```

New in **1.0.13**, all four identity fields are optional. They describe the
host application/integration, not the model. They are forwarded on the
`server.connect` handshake for runtime telemetry attribution. This does not
change authentication or what the runtime records. An unset identity keeps
default attribution.

### 2. Create a text-only session

`create_session` takes `model="gpt-5-mini"`, `streaming=True`,
`available_tools=[]`, and the required permission handler. The empty
allowlist removes tools from this conversation. `approve_all` is only a
trusted-demo convenience, not an authorization system or OS sandbox.

The client manages a runtime subprocess over stdio by default. The published
SDK downloads/caches its matching runtime as needed; it does not install the
interactive `copilot` command. Session creation performs the connection work;
entering the returned session context manager does not create another session.

### 3. Listen while using the completion helper

```python
def on_event(event) -> None:
    match event.data:
        case AssistantMessageDeltaData(delta_content=delta):
            print(delta or "", end="", flush=True)

unsubscribe = session.on(on_event)
try:
    reply = await session.send_and_wait(
        "Explain what the GitHub Copilot SDK is in 3 sentences.",
        timeout=60,
    )
    if reply is None:
        raise RuntimeError("Session became idle without an assistant message.")
finally:
    unsubscribe()
    print()
```

- Register **before** sending so early deltas are observed. Deltas are
  chunks, not a promise of one token per event.
- `send_and_wait` continues delivering events to the listener while it
  watches final messages, idle and session errors.
- It raises `TimeoutError` after the configured wait; `None` means idle
  without an assistant message. Session errors propagate too.
- `finally` unregisters the listener on success, failure or cancellation.
- `asyncio.timeout(180)` bounds the surrounding operation as well.

### 4. Understand cleanup

Exiting the session calls `disconnect()` → **`session.detach`** in 1.0.13:
local handlers are released while persisted session data is retained.
Exiting the owned client stops its runtime process. A timeout by itself
does not abort ongoing remote work; a long-lived client should explicitly
manage `session.abort()` and cancellation.

## Run it

```bash
python examples/01_simple_chat.py
```

Expect a gradually printed explanation; wording, timing and model availability
vary. Failed authentication, transport or model requests should fail visibly,
not produce an apparent successful empty response.

## Try this next

1. Change only the application identity and observe that the answer is not
   prescribed by telemetry metadata.
2. Add a second `send_and_wait` inside the session to reuse conversation
   context. Normal usage/quota accounting still applies.
3. Set `streaming=False` and print `reply.data.content` instead.
4. Use a mock to emit `session.error` or withhold idle; verify cleanup.

## Common pitfalls

- `await session.send(...)` returns a message ID, not the final response.
- A bare `await done.wait()` can hang if no idle event arrives.
- Printing the final message after printing deltas duplicates the answer.
- Never catch `asyncio.CancelledError` and turn it into a successful reply.
- For a Windows legacy console, set `PYTHONIOENCODING=utf-8`.
