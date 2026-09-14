# 07 · Choose a focus, then approve or deny tests

**GitHub Copilot SDK - an introduction**

[Runnable source](07_human_in_the_loop.py) · [Student guide](README.md)

**Sources, SDK v1.0.13:** [elicitation and hooks](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/session.py),
[permission request fields](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/generated/session_events.py),
[permission decisions](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/generated/rpc.py),
[elicitation E2E](https://github.com/github/copilot-sdk/blob/v1.0.13/python/e2e/test_ui_elicitation_e2e.py).

## Goal and boundary

For the review of `examples/01_simple_chat.py`, collect **`errors` or
`cleanup`**, then ask the human whether to run **one fixed command**:

```text
python -m unittest discover -s examples/tests -v
```

The command runs in this repository root. The focus changes the review
choice, **never the command**. No source-reading tool is exposed in this
checkpoint, so the assistant must not claim to have reviewed file contents.

This is a read-only review scenario with one narrowly authorized
test-execution step, not an OS sandbox. Python can write bytecode caches,
and the offline tests create/remove disposable fixtures under `examples/`.
Use only a trusted checkout and environment.

## Two different human interactions

```mermaid
sequenceDiagram
    participant Host
    participant Runtime
    participant Human
    Host->>Runtime: Create structured-first session; inspect tool metadata
    alt Structured ask_user available
        Runtime->>Host: Elicitation form with required string focus
    else Capability unavailable
        Host->>Runtime: Detach unused session; create explicit legacy session
        Runtime->>Host: Freeform question contract
    end
    Host->>Human: Review focus [errors/cleanup]
    Human-->>Host: Validated focus
    Host-->>Runtime: Structured focus or validated freeform answer
    Runtime->>Host: Pre-tool hook for exact command in repository root
    Host-->>Runtime: Ask permission; no shell reuse or command variation
    Runtime->>Host: PermissionRequestShell with tool_call_id
    Host->>Human: Approve this one exact command? [y/N]
    alt y
        Host-->>Runtime: PermissionDecisionApproveOnce
        Runtime-->>Host: Matching test-command result
        Host->>Host: Check ID, success, and actual unittest summary
    else n, empty, or input unavailable
        Host-->>Runtime: Reject or UserNotAvailable
        Host->>Host: Record denial; do not claim execution
    end
```

## Validate the input contract

`FOCUS_SCHEMA` requests an object with one required string property:

```python
{
    "type": "object",
    "properties": {"focus": {"type": "string", "enum": ["errors", "cleanup"]}},
    "required": ["focus"],
    "additionalProperties": False,
}
```

`is_focus_form` rejects URL mode, unexpected fields/types/constraints, and
unrecognized enum values. `validate_focus` trims and normalizes case, then
accepts only `errors` or `cleanup`. It never accepts arbitrary “review
instructions” or shell fragments.

`ReviewHost.on_elicitation_request` returns, for example:

```python
{"action": "accept", "content": {"focus": "errors"}}
```

Unexpected schemas decline. Three invalid answers, EOF, timeout, or
unavailable input cancel the form. A second focus request cannot start
another interactive collection.

`has_structured_ask_user` initializes tools and checks current metadata for
an `ask_user` schema containing both `message` and `requestedSchema`.
The SDK accepting `ask_user_variant="elicitation"` is not capability proof.
If the tool is absent or legacy-shaped, the unused session is detached and
a new session explicitly uses:

```python
ask_user_variant="legacy",
on_user_input_request=host.on_user_input_request,
```

The fallback accepts a freeform-only question with no choices and runs the
**same focus validator**. Timeout/EOF fails visibly; it is not an answer or
an approval. A metadata-only inspection on the pinned local runtime found
no structured `ask_user` in the requested catalogue. This is not a claim
that either interactive path was live-tested during the offline update.

## Authorize one literal action

`EXPECTED_COMMAND` is a constant. `is_expected_command` rejects shell
metacharacters and requires **exact string equality**; even extra whitespace,
quoting, additional flags, or `python3` instead of `python` are rejected.
`shlex.split` alone would not establish shell safety.

The pre-tool hook additionally requires:

- `workingDirectory == str(REPO_ROOT)`;
- only the platform's `bash`/`powershell` tool after a validated focus;
- no `shellId`, working-directory override, detach, or async mode;
- synchronous execution, with the requested `initial_wait=120`.

It returns `None` for this narrow request so the runtime continues through its
normal typed shell permission check. Returning `permissionDecision="ask"` would
create a separate hook permission request, not `PermissionRequestShell`.
The permission callback independently validates the runtime's `full_command_text`, rejects
write redirection, URLs, sandbox bypass, missing call IDs, and repeat
decisions. It reads the actual **`PermissionRequestShell.tool_call_id`**;
pre-tool hooks do not have that field in SDK 1.0.13.

Only `y` returns `PermissionDecisionApproveOnce()`. Anything else returns
`PermissionDecisionReject`; EOF/timeout returns
`PermissionDecisionUserNotAvailable`. Managed-approval requests still
require the explicit human decision. No session-wide grant is offered.

## Host evidence, not model wording

`ReviewHost` holds the validated focus, decision and request ID, plus
matching typed start/completion events. `report_outcome()` requires:

1. the expected shell tool and arguments;
2. the same ID on the host decision, start, and completion;
3. explicit approve-once, successful completion, and actual result content;
4. the result's unittest summary reporting at least one test and `OK`.

The actual command output is printed under `[command result]`. A generic
tool-success flag, missing result, “tests passed” model prose, a zero-test
run, or an unmatched ID cannot print `COMMAND_RESULT_VERIFIED`.
If the command was denied, only a denial is reported, not proof of execution
or non-execution. Assistant text is separately labeled `[agent commentary]`.

## Run both decisions

```bash
python examples/07_human_in_the_loop.py
# Choose errors, then n.
python examples/07_human_in_the_loop.py
# Choose cleanup, then y.
```

**Illustrative denial trace — not an observed run:**

```text
[hitl] focus accepted: errors
[tool] bash started id=<id>
[permission] proposed command (id=<id>): python -m unittest discover -s examples/tests -v
[permission] working directory: <repository root>
Approve this one exact command? [y/N]: n
[host] COMMAND_DENIED id=<id> reason=user rejected
[tool] completed id=<id> success=False
[host] COMMAND_DENIAL_RECORDED id=<id>; no execution claimed
```

**Illustrative approved trace — not an observed run:**

```text
[hitl] focus accepted: cleanup
[host] COMMAND_APPROVE_ONCE id=<id>
[tool] completed id=<id> success=True
[command result]
<actual unittest output, including Ran N tests and OK>
[host] COMMAND_RESULT_VERIFIED id=<id>; unittest reported OK
```

Exact additional host trace forms:

```text
[host] COMMAND_DENIED id=<id-or-missing> reason=outside the one-command policy
[host] COMMAND_DENIED id=<id> reason=input unavailable or timed out
[host] COMMAND_INCOMPLETE reason=<exception message>
[host] COMMAND_CANCELLED; no result verified
```

Cancellation is re-raised, not converted into a denied/successful result.
`_console_input.read_answer` serializes stdin, bounds each read to 120
seconds, and refuses another reader after interruption. A 300-second turn
deadline and 360-second outer deadline bound the overall interaction.

**Exercise:** mock a correct command result under a different ID. Approval
and success somewhere in the same conversation must not pass verification.
