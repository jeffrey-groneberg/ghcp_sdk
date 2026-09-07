# 07 · Human in the loop

📖 **Sources (SDK v1.0.13):**
[Python permission/input handlers](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/session.py),
[generated request variants](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/generated/session_events.py),
[decision objects](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/generated/rpc.py),
[`ask_user` release notes](https://github.com/github/copilot-sdk/releases/tag/v1.0.13).

Open [the runnable source](07_human_in_the_loop.py). One callback supplies
information, while the other decides whether a requested action may run.
This is a bounded interactive teaching adapter, not a production approval UI.

## The flow

```mermaid
sequenceDiagram
    participant App
    participant Runtime
    participant Human
    App->>Runtime: create_session(ask_user_variant=legacy, callbacks)
    App->>Runtime: send_and_wait(ask name, print fixed greeting)
    Runtime->>App: UserInputRequest
    App->>Human: Ask name, 30-second deadline
    Human-->>App: Name
    App-->>Runtime: answer + wasFreeform
    Runtime->>App: PermissionRequestShell
    App->>Human: Show command; approve once? [y/N]
    Human-->>App: y or denial
    App-->>Runtime: ApproveOnce or Reject
    Note over Runtime: Only execute if runtime policy permits
    Runtime-->>App: Final answer, then idle
```

## Code walkthrough

### 1. Select the correct input contract

```python
ask_user_variant="legacy",
on_user_input_request=on_user_input_request,
on_permission_request=on_permission_request,
```

**New in 1.0.13**, `ask_user_variant` accepts `"legacy"` (the default) or
`"elicitation"`. This demo makes the legacy question/answer shape explicit.
The structured alternative needs **`on_elicitation_request`**, not the
legacy callback copied unchanged. Re-supply callbacks on cold resume.

The session exposes only `builtin:ask_user` and the platform's shell tool
(`builtin:bash` or Windows `builtin:powershell`). No file or MCP tools are
needed. A permission callback runs when the runtime requests a decision;
it is not a promise that every tool call produces a fresh prompt.

### 2. Return typed permission decisions

```python
match request:
    case PermissionRequestShell(full_command_text=command):
        print(f"\n[permission] proposed command:\n{command}")
    case _:
        return PermissionDecisionReject(
            feedback="Only the reviewed greeting command is in scope."
        )
```

The SDK request is a discriminated union. Useful variants include
`PermissionRequestShell`, `PermissionRequestRead`, `PermissionRequestWrite`
and `PermissionRequestMcp`. In **1.0.13** their generated classes **do have
a string `kind` ClassVar**. Do not use the old enum-style `request.kind.value`;
pattern matching makes each variant's fields explicit.

The callback awaits the human and returns:

- `PermissionDecisionApproveOnce()` only for an explicit `y`.
- `PermissionDecisionReject(feedback=...)` for rejection, unknown variants
  or unavailable/timed-out console input.

These are objects from `copilot.rpc`, not old `{"kind": "approve-once"}`
dictionaries. No reads are automatically trusted: reading local files can
expose secrets. Managed runtime policies can still deny an approved action.

### 3. Respect choices and freeform input

`UserInputRequest` is a TypedDict with `question`, optional `choices` and
`allowFreeform` (default `True`). The handler displays choices and applies:

| Input | Returned response |
|---|---|
| Valid numbered choice, e.g. `2` | Selected **choice text**, `wasFreeform=False` |
| Exact choice text | That text, `wasFreeform=False` |
| Other non-empty text, if freeform is permitted | Entered text, `wasFreeform=True` |
| Blank or invalid answer when freeform is forbidden | Prompt again, at most three attempts |
| No choices and freeform forbidden | Visible validation error |

The return shape is always:

```python
{"answer": "selected or entered text", "wasFreeform": False}  # or True
```

Do not return `"2"` when the protocol expects the actual selected label.
Do not silently accept arbitrary text when `allowFreeform=False`.

### 4. Keep human waits bounded and cancellable

`read_answer` serializes console prompts with an async lock. A daemon
thread performs blocking `input`, while the event loop polls a thread-safe
queue and enforces a **30-second timeout**. This avoids blocking SDK events.

Why not simply `await asyncio.to_thread(input, ...)`? Cancelling that await
does not cancel the thread's stdin read, and `asyncio.run` may then wait for
its default executor at shutdown. A daemon reader does not hold process
exit open. After EOF, timeout or cancellation the adapter disables further
reads, rather than creating competing stdin readers. Restart the script to
recover console input.

The helper re-raises `asyncio.CancelledError`. Permission timeouts deny;
input-request failures are reported visibly and propagated. The final model
wait is bounded to 180 seconds and the whole operation to 240 seconds.
The three-attempt validation limit prevents an endless invalid-answer loop.

### 5. Keep shell code separate from the user's answer

The prompt requests a **fixed literal greeting** in the shell. The user's
name belongs in the final assistant response, not interpolated shell code.
Review the proposed command before approving; a natural-language request is
not enforcement. Deny anything unexpected, and never enter credentials.

## Run it

```bash
python examples/07_human_in_the_loop.py
```

Illustrative session:

```text
[agent asks] What is your name?
Your answer (choice number or text): Ada
[permission] proposed command:
printf '%s\n' 'Hello from the Copilot SDK.'
Approve this one command? [y/N]: y
[agent] Hello, Ada! The command printed: Hello from the Copilot SDK.
```

The exact command varies by model/platform. A denial may lead to a refusal
or another proposed approach; the model's subsequent behavior is not
guaranteed. This example continues to deny unexpected permission variants.

## Try this next

1. Ask for a greeting language with choices and `allowFreeform=False`.
2. In tests, exercise a numeric choice, exact choice, invalid input,
   freeform input, EOF and timeout.
3. Replace the terminal adapter with a UI-backed awaitable that can
   genuinely cancel or expire pending questions.
4. Record decision type and correlation IDs without storing secrets.

## Common pitfalls

- Human input and permission approval are separate contracts.
- `approve_all` from the earlier trusted demos is not a secure default.
- Blocking `input()` directly inside a callback prevents async deadlines
  and event delivery from progressing.
- A timeout does not inherently abort remote agent work; long-lived
  clients must design explicit cancellation.
