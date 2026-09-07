# 06 · Session persistence

📖 **Sources (SDK v1.0.13):**
[Python create/resume implementation](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/client.py),
[session ID and detach](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/session.py),
[release lifecycle changes](https://github.com/github/copilot-sdk/releases/tag/v1.0.13).

Open [the runnable source](06_session_resume.py). Run once to supply two
facts, then resume in a new process without repeating those facts in the
new prompt. Tools are disabled in both phases so the agent cannot read the
answers from this source file.

## The flow

```mermaid
sequenceDiagram
    participant First as First process
    participant Runtime
    participant Disk as CLI session storage
    participant Second as New process
    First->>Runtime: create_session(session_id=demo-session-resume)
    First->>Runtime: send_and_wait(remember two facts)
    Runtime->>Disk: Persist conversation
    Runtime-->>First: Acknowledgement
    First->>Runtime: disconnect -> session.detach
    Note over First,Second: First client exits; same account/storage retained
    Second->>Runtime: resume_session(same ID, callbacks and tool scope)
    Runtime->>Disk: Load persisted conversation
    Second->>Runtime: send_and_wait(recall question)
    Runtime-->>Second: Answer using previous context
```

## Code walkthrough

### 1. Choose or save an ID

```python
SESSION_ID = "demo-session-resume"
```

The command-line `--session-id` option allows separate workshop conversations.
A real application should use a unique conversation identifier and authorize
which user may access it. An ID is not an authorization boundary.

**Generated IDs are resumable too.** If `session_id` is omitted, save
`session.session_id` (not `session.id`), or inspect
`await client.list_sessions()` and each result's `session_id`. The tagged
Python implementation takes precedence over old upstream prose claiming
that generated IDs cannot be retrieved.

### 2. Create, then detach

```python
session_ctx = await client.create_session(
    on_permission_request=PermissionHandler.approve_all,
    model="gpt-5-mini",
    session_id=session_id,
    available_tools=[],
)
```

The first prompt supplies the name and language. After a bounded turn,
exiting `async with session_ctx` calls `disconnect()`. In **1.0.13** this
uses `session.detach`, leaving persisted conversation/planning state intact.
The owned client then shuts down. `client.delete_session(id)` is the
explicit destructive operation; this demo never calls it.

### 3. Cold resume with explicit runtime wiring

```python
session_ctx = await client.resume_session(
    session_id,
    on_permission_request=PermissionHandler.approve_all,
    available_tools=[],
)
```

The resume prompt asks what the user said earlier, without supplying the
answers. The model reads prior conversation context; “without re-reading
the earlier message” would be a misleading way to describe persistence.

`model=` **is supported on resume** in 1.0.13. Omitting it retains the prior
model; specifying it requests a change. Do not claim changing models is
unsupported or silently ignored.

### 4. Know what must be re-established

| Category | Resume behavior / responsibility |
|---|---|
| Conversation history and persisted planning artifacts | Loaded from the same runtime session storage; not arbitrary host memory |
| Model | Retained if omitted; `model=` can request an override |
| Custom Python tools, permission/input handlers, hooks | Re-register implementations/callbacks in the new process |
| MCP connections, custom agent configuration, tool scope | Re-supply the required configuration rather than assuming every startup option persists |
| Application variables, credentials and authorization | Re-establish explicitly; session history is not a credential store |
| Injected `managed_settings` (1.0.13) | Startup-only, not persisted; **re-supply on resume** or the injected layer is cleared |

Managed policy injection is permissions-only and requires CLI **1.0.79-5+**;
this workshop's release-matched runtime is **1.0.83**. It composes
restrictively with device/server policy rather than overriding it.

## Run it

```bash
python examples/06_session_resume.py --session-id workshop-alice
python examples/06_session_resume.py --resume --session-id workshop-alice
```

Illustrative second output:

```text
Session ID: workshop-alice
Your name is Jeffrey, and your preferred programming language is Python.
```

This demonstrates a model recall task, not a cryptographic proof or a
guarantee of verbatim history retention. Long conversations may be compacted;
use explicit application storage for facts that must be recalled exactly.

## Try this next

1. Omit `session_id` in a copy of the example and persist the returned
   `session.session_id`.
2. Try `--resume` with an unknown ID and verify the failure is visible.
3. Pass an available `model=` on resume and inspect the selected model.
4. Re-register a custom tool on resume, keeping its source-qualified name
   in the tool allowlist.

## Common pitfalls

- Use the same account and CLI state location. A new container without the
  old persisted storage does not acquire history merely from the ID.
- Run create once, then resume. Use a new ID for a fresh conversation rather
  than depending on duplicate-create semantics.
- A timeout raises `TimeoutError`, not `None`; this example fails visibly
  on either timeout or an absent final message.
- Do not claim that all system prompts, agents, credentials and session
  options are automatically persisted.
