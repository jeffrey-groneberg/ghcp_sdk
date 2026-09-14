# 01 · Stream a repository-review plan

**GitHub Copilot SDK - an introduction**

[Runnable source](01_simple_chat.py) · [Student guide](README.md)

**Sources, SDK v1.0.13:** [Python session](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/session.py),
[client identity](https://github.com/github/copilot-sdk/blob/v1.0.13/docs/features/client-info.md),
[streaming events](https://github.com/github/copilot-sdk/blob/v1.0.13/docs/features/streaming-events.md).

## Goal and boundary

Ask for a review plan for `examples/01_simple_chat.py` in
`jeffrey-groneberg/ghcp_sdk`, focusing on **error handling and cleanup**.
This first checkpoint supplies a short repository description as text.
`available_tools=[]` means the model cannot inspect the file: this is a
**plan based on supplied context, not a completed source review**.

```mermaid
sequenceDiagram
    participant Host
    participant Runtime
    Host->>Runtime: create_session(streaming=True, available_tools=[])
    Host->>Host: Register event listener
    Host->>Runtime: Supplied description + review-plan prompt
    loop Text chunks
        Runtime-->>Host: assistant.message_delta
    end
    Runtime-->>Host: assistant.message, then session.idle
    Host->>Host: Require final message; unsubscribe in finally
    Host->>Runtime: Detach session; stop owned client
```

## Important code

`REPOSITORY_DESCRIPTION` explicitly names the workshop, target file, and
client/session/subscription lifecycle. The prompt says not to claim file
access or actual bugs. No model is pinned; the runtime chooses its default.

The optional `client_info` identifies **this application**, not a model or
credential. The four application/integration fields are forwarded during the
runtime connection. They do not change authorization.

Register before sending, then combine streaming with bounded completion:

```python
unsubscribe = session.on(on_event)
try:
    reply = await session.send_and_wait(REVIEW_PROMPT, timeout=60)
    if reply is None:
        raise RuntimeError("Session became idle without an assistant message.")
    if not saw_delta:
        print(reply.data.content, end="", flush=True)
finally:
    unsubscribe()
    print()
```

`REVIEW_PROMPT` contains the supplied description and the explicit instruction
not to claim file access. `AssistantMessageDeltaData.delta_content` is a
chunk, not necessarily one token. The final message is required even when
chunks were printed. If no nonempty deltas arrive, the final content is
printed; otherwise printing it again would duplicate the answer.

- `send_and_wait` raises on timeout/session error. `None` means idle without
  an assistant message; it is not timeout or success.
- The outer `asyncio.timeout(180)` also bounds setup and the surrounding run.
- `finally` handles partial output, failures, and cancellation.
- Session exit calls `disconnect()` → `session.detach` in 1.0.13. Persisted
  state remains. Client exit stops its owned runtime process.
- A wait timeout is not proof that remote work was aborted. A long-lived
  host must deliberately manage `session.abort()` and lifecycle cleanup.

## Run and inspect

```bash
python examples/01_simple_chat.py
```

**Illustrative expected answer, not an observed model run:**

```text
Based only on the supplied description:
1. Check how timeouts and session errors are surfaced.
2. Require a final assistant message rather than accepting idle alone.
3. Check that subscriptions and client/session resources are released.
```

Offline regressions test real SDK wait semantics, required final replies,
streaming, listener cleanup, and propagated cancellation. They do not
establish model quality or live authentication.

**Exercise:** withhold a final message in a mock after emitting a delta.
The example must fail rather than treat partial text as a finished review.
