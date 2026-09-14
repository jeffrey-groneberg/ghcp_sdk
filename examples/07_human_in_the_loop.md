# 07 · Human in the loop

📖 **Sources (SDK v1.0.13):**
[Python elicitation and permission types](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/session.py),
[generated permission variants](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/generated/session_events.py),
[official elicitation E2E](https://github.com/github/copilot-sdk/blob/v1.0.13/python/e2e/test_ui_elicitation_e2e.py).

Open [the runnable source](07_human_in_the_loop.py). It demonstrates two
separate human decisions:

1. prefer a narrowly validated structured form, with an explicit legacy
   fallback when the runtime does not expose the structured `ask_user` tool;
2. approve or reject one exact harmless shell command.

The terminal adapter is intentionally small. A production application should
replace it with its own UI, identity, audit, and authorization layer.

## The flow

```mermaid
sequenceDiagram
    participant App
    participant Runtime
    participant Human
    App->>Runtime: create_session(ask_user_variant=elicitation)
    App->>Runtime: Inspect current tool metadata
    alt structured ask_user available
        Runtime->>App: elicitation.requested + JSON Schema
        App->>App: Validate exact expected schema
    else structured tool unavailable
        App->>Runtime: Detach; create legacy ask_user session
        Runtime->>App: UserInputRequest
        App->>App: Validate freeform-only name contract
    end
    App->>Human: Ask for name, 120-second deadline
    Human-->>App: Name
    App-->>Runtime: action=accept, content.name
    Runtime->>App: PermissionRequestShell
    App->>App: Match exact allowlisted command
    App->>Human: Approve once? [y/N]
    Human-->>App: y or denial
    App-->>Runtime: ApproveOnce / Reject / UserNotAvailable
    Runtime-->>App: Final answer, then idle
```

## Code walkthrough

### 1. Prefer structured elicitation when the UI can validate forms

```python
ask_user_variant="elicitation",
on_elicitation_request=on_elicitation_request,
```

The default `"legacy"` variant still uses `on_user_input_request` with
`question`, `choices`, and `allowFreeform`. This sample first requests the
newer structured shape because the host can validate the JSON Schema before
collecting data.

The callback accepts only:

- form mode, never a URL redirect;
- one object property named `name`;
- a required, string-typed value;
- a local length limit of 1–80 characters.

Unexpected schemas return `{"action": "decline"}`. Timeout/EOF returns
`{"action": "cancel"}`. A valid response uses:

```python
{"action": "accept", "content": {"name": "Ada"}}
```

This is deliberately narrower than a generic form renderer. Human-in-the-loop
does not mean accepting any data request the model invents.

The SDK option alone is not proof that the bundled runtime exposed the tool.
The sample calls `session.rpc.tools.initialize_and_validate()` and inspects
`get_current_metadata()`. It requires an `ask_user` schema with both `message`
and `requestedSchema`; an absent tool or legacy `question` schema triggers the
fallback. The unused session is detached, then a legacy session accepts only
one non-empty freeform name and no choices. Live validation with runtime
1.0.83 exercised this fallback.

### 2. Validate policy before asking the human

The permission callback pattern-matches `PermissionRequestShell`, rejects
every other permission kind, rejects sandbox-bypass requests, and validates
`full_command_text` against one platform-specific policy:

```python
EXPECTED_COMMAND = "printf '%s\\n' 'Hello from the Copilot SDK.'"
```

On POSIX, `shlex.split` must produce exactly `printf`, the fixed format string,
and the fixed literal; alternate quoting is allowed but extra operators or
arguments are not. Only after that machine check does it ask the human.
An explicit `y` returns `PermissionDecisionApproveOnce()`. Every other answer
returns `PermissionDecisionReject(...)`.

This ordering matters: a human dialog is not a replacement for application
policy. Keep the decision scope as small as possible and prefer approve-once
over session-wide or permanent grants.

### 3. Treat managed approval as a real human gate

Permission variants can set `managed_approval_required=True`. The sample
surfaces that fact and still requires the explicit terminal answer; it never
auto-approves a managed request. If input is unavailable, it returns
`PermissionDecisionUserNotAvailable()` rather than pretending the action was
rejected by a present user.

Longer-lived approval variants exist, but this sample intentionally does not
offer them.

### 4. Keep terminal waits serialized, bounded, and cancellable

Both interactive examples use `_console_input.read_answer`. A daemon thread
performs blocking `input()`, while the event loop polls a thread-safe queue
under an async lock. Every prompt has a 120-second workshop deadline.

After EOF, timeout, or cancellation, the helper refuses to start another stdin
reader in the same process. This avoids overlapping readers and avoids
`asyncio.run()` waiting forever for a cancelled `to_thread(input, ...)`.
`asyncio.CancelledError` is re-raised.

### 5. Scope the tool catalogue

```python
available_tools=ToolSet().add_builtin(["ask_user", SHELL_TOOL])
```

No file, MCP, web, or unrelated shell-adjacent tools are exposed. Tool
allowlists, permission callbacks, and prompts are separate controls; none is
an OS sandbox. Example 08 adds the runtime sandbox layer.

## Run it

```bash
python examples/07_human_in_the_loop.py
```

Illustrative session:

```text
[hitl] Structured ask_user is unavailable in this runtime; falling back to the legacy question contract.
[tool] ask_user started
[agent asks] What is your name?
Your name: Ada

[tool] bash started
[permission] proposed command:
printf '%s\n' 'Hello from the Copilot SDK.'
Approve this one exact command? [y/N]: y

[agent] Hello, Ada! The command printed: Hello from the Copilot SDK.
```

The runtime may use the structured path instead. In both paths, the model must
request the expected name contract and allowed command. A variation is denied
rather than silently widened.

## Try this next

1. Add a second allowlisted form with an enum and validate the selected value.
2. Replace terminal input with a UI-backed future that can genuinely expire.
3. Record decision type and correlation IDs without storing submitted content.
4. Test with a runtime that exposes structured `ask_user`, then verify both
   branches return the same application-level result.

## Common pitfalls

- Information requests and action permissions are different contracts.
- Do not assume an accepted SDK option means the runtime exposed that tool;
  inspect capabilities or metadata and design an explicit fallback.
- Do not render arbitrary URL elicitation without a trusted navigation policy.
- Do not ask the human until the application has validated the request.
- Do not convert timeout, cancellation, or missing input into approval.
- Approval does not imply sandbox bypass; bypass is a separate decision.
