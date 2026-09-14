# 08 · A denied vault and one approved exception

**GitHub Copilot SDK - an introduction**

[Runnable source](08_sandbox.py) · [Student guide](README.md)

**Sources, SDK v1.0.13:** [official sandbox-bypass E2E](https://github.com/github/copilot-sdk/blob/v1.0.13/nodejs/test/e2e/sandbox_bypass.e2e.test.ts),
[sandbox configuration](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/generated/rpc.py),
[permission/event types](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/generated/session_events.py),
[pre-tool hook types](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/session.py).

## Goal and boundary

Demonstrate denied versus explicitly approved access to a **private
repository-review note** about `examples/01_simple_chat.py`. The note is
fresh disposable teaching data, **not an actual secret**.

`main()` creates `examples/copilot-sdk-review-<generated>/vault/review-note.txt`
and uses that generated workspace as the runtime working directory.
The vault is denied by the sandbox and removed when the run exits.
No system temporary directory, real credentials, or private user files
are used.

The sandbox API is experimental. The official tagged E2E limits its
execution to a supported macOS backend. Other environments need their own
supported backend; for example, Linux deployments may need Bubblewrap.
An installed executable alone does not prove backend availability or
effective enforcement. Missing backend support is an **incomplete/failing
demo**, never a reason to grant special container privileges or disable
security controls.

```mermaid
sequenceDiagram
    participant Host
    participant Runtime
    participant Sandbox
    participant Human
    Host->>Host: Write disposable note with an unpredictable suffix
    Host->>Runtime: Inspect grep metadata; enable sandbox; deny vault
    Host->>Runtime: Request one exact content-mode grep (no suffix in prompt)
    Runtime->>Host: Pre-hook validates exact arguments
    Runtime->>Sandbox: Scoped read
    Sandbox-->>Runtime: Denied path
    Runtime->>Host: Bypass request with actual tool_call_id
    Host->>Human: Approve this one grep outside sandbox? [y/N]
    alt y
        Host-->>Runtime: ApproveOnce for that request
        Runtime-->>Host: Matching successful result containing full private note
        Host->>Host: Verify approval + ID + actual note content
    else denied or input unavailable
        Host-->>Runtime: Reject / UserNotAvailable
        Runtime-->>Host: Matching failed tool completion
        Host->>Host: Record denial without claiming access or containment
    end
```

The diagram is an intended supported-backend flow, not a claim that every
OS or runtime emitted it during validation.

## Configure the boundary

`sandbox_runtime_env()` copies the inherited environment, preserves other
feature flags, and adds `SANDBOX`. It does not replace `PATH` or remove
security settings.

The high-level Python session constructor does not take a sandbox argument
in 1.0.13; the sample uses the generated options RPC:

```python
await session.rpc.options.update(
    SessionUpdateOptionsParams(
        sandbox_config=SandboxConfig(
            enabled=True,
            allow_bypass=True,
            add_current_working_directory=True,
            user_policy=SandboxConfigUserPolicy(
                filesystem=SandboxConfigUserPolicyFilesystem(
                    denied_paths=[str(state.vault)],
                ),
                network=SandboxConfigUserPolicyNetwork(
                    allow_local_network=False,
                    allow_outbound=False,
                ),
            ),
        ),
    )
)
```

The runnable code checks `updated.success`; a rejected configuration raises.
`allow_bypass=True` permits a request for an exception, **not automatic
approval**. The callback offers exactly one human bypass decision.
Only built-in `grep` is exposed. There is no shell or Python custom tool
available to the model.

## Require matching content, not generic success

A metadata-only inspection of the pinned local runtime confirmed:

| Grep input | Meaning used here |
|---|---|
| `pattern` | Exact anchored prefix, `^WORKSHOP_PRIVATE_REVIEW_NOTE ` |
| `paths` | Exact absolute disposable-vault directory |
| `glob` | Only `review-note.txt` |
| `output_mode` | **`content`**, not the default `files_with_matches` |
| `-n` | `True`, include matching line numbers |
| `head_limit` | `1`, bound output |

`require_content_grep` checks the live schema before sending a model prompt.
`scoped_grep_hook` permits only one request with exactly those arguments in
the generated workspace; variations are explicitly denied.

`make_review_note()` appends `secrets.token_hex(16)` to the note. The complete
line is held in `ApprovalState.note_content`, but **neither the suffix nor
the full note is supplied in the model prompt**:

```text
WORKSHOP_PRIVATE_REVIEW_NOTE file=examples/01_simple_chat.py; focus=error handling; check final-message handling and listener cleanup; nonce=<unpredictable 32 hex characters>
```

Echoing the requested prefix, returning a filename, reporting no matches,
or merely setting `success=True` cannot prove access to that line. There
is no “success without marker” fallback.

Previous speculation that missing Linux content meant redaction was
**not established**. Grep's filenames-only default and other possible
results make such an inference invalid. This version requests content and
fails if the actual content evidence is missing; it does not infer
undocumented platform behavior.

## Scope and correlate the human decision

The permission handler accepts only `PermissionRequestRead` for the exact
vault or its note, with a nonempty **`request.tool_call_id`**.
An ordinary scoped read approval is logged with `bypass=False`; normal
sandbox restrictions still apply. A managed ordinary-read approval that
would need another human gate fails closed.

For `request_sandbox_bypass=True`, the host shows the reason, path, and ID.
Only `y` returns `PermissionDecisionApproveOnce`; denial and missing input
are separately recorded. Repeated bypass requests are rejected.

The approval ID comes from the real permission request, not the latest
observed start event. SDK 1.0.13's pre-tool hook input has **no call-ID
field**, so the hook is not used as an approval/correlation record.

`bypass_verified(state)` requires all of:

1. the exact scoped hook request and explicit bypass approval;
2. that approval's ID on the expected grep start;
3. a successful completion with the **same ID**, no error, and a result;
4. the **entire private note, including the unpredictable suffix**, in
   that result's `content`.

`ToolExecutionCompleteData.sandboxed` is logged as runtime telemetry only.
Neither `True` nor `False` proves whether a bypass executed outside the
backend. Approval plus matching successful content is required regardless
of that field.

Missing request, backend, start, completion, result, or full note is
incomplete/failure. Unapproved content is also failure, not a successful
security demonstration. A host denial record does not prove that the
underlying OS prevented every possible access.

## Run both decisions

```bash
python examples/08_sandbox.py
# Answer n for the disposable-data bypass.
python examples/08_sandbox.py
# On a supported backend, answer y in a separate run.
```

**Illustrative denial trace — not an observed sandbox run:**

```text
[sandbox] grep content-output metadata confirmed
[tool] grep started id=<id> scoped=True
[sandbox bypass] <runtime reason>
Target: <repository>/examples/copilot-sdk-review-<generated>/vault
Tool call ID: <id>
Run this one grep outside the sandbox? [y/N]: n
[host] SANDBOX_BYPASS_DENIED id=<id> reason=user rejected
[tool] completed id=<id> success=False sandboxed=<telemetry>
[host] SANDBOX_DENIAL_RECORDED id=<id>; no access claimed
```

**Illustrative approved trace — not an observed sandbox run:**

```text
[host] SANDBOX_BYPASS_APPROVE_ONCE id=<id>
[tool] completed id=<id> success=True sandboxed=<telemetry>
[host] SANDBOX_BYPASS_VERIFIED id=<id>; matching result contains the private note
```

The sample does not print the model's commentary about sandbox access. That
commentary can disagree with the host's recorded callback and result; it is
not security evidence.

Exact additional host trace forms:

```text
[host] SANDBOX_SCOPED_READ_APPROVE_ONCE id=<id>; bypass=False
[host] SANDBOX_BYPASS_DENIED id=<id-or-missing> reason=outside the scoped read policy
[host] SANDBOX_BYPASS_DENIED id=<id> reason=managed read approval unavailable
[host] SANDBOX_BYPASS_DENIED id=<id> reason=only one bypass decision is allowed
[host] SANDBOX_BYPASS_DENIED id=<id> reason=input unavailable or timed out
[host] SANDBOX_INCOMPLETE reason=<exception message>
[host] SANDBOX_CANCELLED; no access verified
```

For an approved search without the private note, the exact failure reason is:

```text
[host] SANDBOX_INCOMPLETE reason=Approved grep lacks a matching successful result containing the private note.
```

The entire run is bounded, callbacks propagate cancellation, and the listener
and disposable vault are cleaned up on success, denial, or failure.

## What offline tests do and do not prove

The suite uses real permission/event/configuration types, invokes the actual
host callbacks, and supplies mocked runtime results. Negative controls cover
filenames-only output, no matches, echoed query, missing nonce/result,
mismatched approval/completion IDs, failed execution, unapproved access,
wrong scope, missing backend, and repeated requests.

These tests prove host verification logic, **not real sandbox enforcement**.
Live approval/denial runs remain necessary on each intended environment.
Runtime sandboxing also does not isolate the host Python process, supply
tenant authorization, or replace container/VM boundaries. Production hosts
need their own isolation, credential, audit, and identity design.
