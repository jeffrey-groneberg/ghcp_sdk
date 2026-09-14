# GitHub Copilot SDK - an introduction

## One scenario, eight independent checkpoints

Build understanding of a **read-only repository assistant** reviewing this
workshop repository, `jeffrey-groneberg/ghcp_sdk`, especially
`examples/01_simple_chat.py`, for **error handling and cleanup**.

The eight numbered Python files are independently runnable learning
checkpoints, **not a cumulative production application**. Each walkthrough
explains what context or capability was added and what the host can verify.
07 adds one explicitly approved offline-test command; 08 uses a disposable
private review note rather than real secrets. Neither edits repository source.

**Baseline:** Python 3.11+, `github-copilot-sdk==1.0.13`, Pydantic 2+,
matching Copilot CLI/runtime **1.0.83**. See [repository setup](../README.md).
Run commands from the repository root with that environment active.

| Checkpoint | Review task | Host evidence |
|---|---|---|
| [01 · Streaming](01_simple_chat.md) | Plan a review from an explicitly supplied repository description | Required final message, streamed text, bounded wait and cleanup; **no file-read claim** |
| [02 · Custom tool](02_custom_tools.md) | Read deterministic AST metadata for an allowlisted sample | Actual `inspect_python_file(FileParams)` handler result |
| [03 · Custom agents](03_custom_agents.md) | Research, then review the same file | Checked `agent.get_current().agent.name` before each role's turn |
| [04 · Hooks](04_hooks.md) | Observe a source read | Pre/success/failure logs plus a matching successful `view` result |
| [05 · GitHub MCP](05_mcp_servers.md) | Fetch this repository's issues as review context | Correct repository arguments plus matched MCP start/success/result IDs |
| [06 · Persistence](06_session_resume.md) | Save and cold-resume the review file and focus | Two-process recall exercise; resumed prompt omits both fact values |
| [07 · Human input](07_human_in_the_loop.md) | Validate a focus; approve or deny one fixed unit-test command | Host decision, exact call ID, and actual test output; structured/legacy input paths |
| [08 · Sandbox](08_sandbox.md) | Approve or deny access to a disposable private review note | Explicit bypass approval and matching successful grep result containing the full nonce-bearing note |

## Run the checkpoints

```bash
python examples/01_simple_chat.py
python examples/02_custom_tools.py
python examples/03_custom_agents.py
python examples/04_hooks.py
python examples/05_mcp_servers.py
python examples/06_session_resume.py --session-id workshop-review-1
python examples/06_session_resume.py --resume --session-id workshop-review-1
python examples/07_human_in_the_loop.py
python examples/08_sandbox.py
```

For 07, choose `errors` or `cleanup`, then try `n` in one run and `y` in
another. The command is always:

```text
python -m unittest discover -s examples/tests -v
```

For 08, choose `n` and `y` in separate runs on a supported sandbox backend.
The temporary vault stays under `examples/` and is removed on exit. Never
use real credentials or personal/private source as the teaching note.
Missing backend or missing content evidence is **incomplete**, not success.
Do not bypass environment security controls to make the demo pass.

## Shared conventions

- No sample pins a model; the runtime chooses its current default. Inspect
  `await client.list_models()` before making a deliberate account-supported
  model choice. Live calls can consume quota.
- Every turn requires a final message. `send_and_wait` raises on timeout or
  session error; `None` means idle without an assistant message.
- Deltas and tool events continue to arrive while `send_and_wait` waits.
  Subscriptions are removed in `finally`; cancellation is propagated.
- Context managers detach the session and stop an owned client. In 1.0.13,
  detach retains persisted state. A timeout alone is not remote abort.
- `available_tools` filters the **entire** merged catalogue, for example
  `builtin:view`, `custom:inspect_python_file`, `mcp:github-list_issues`.
- Exposure filters, logging hooks, application permission decisions and
  runtime sandboxing are different controls. `approve_all` in trusted
  non-sensitive checkpoints is not isolation.
- Custom Python tools execute in the host process, not automatically in
  the runtime sandbox.
- `_tool_trace.py` is only a small start/completion recorder; it is not a
  policy engine. `_console_input.py` serializes bounded, cancellable input.
- MCP authentication is separate from model authentication. The header is
  constructed from the resolved token; neither token nor headers are logged.
- Model commentary is not authoritative evidence of host approvals or
  successful operations. Read the host traces and actual results.

## Verification and source authority

```bash
python -m unittest discover -s examples/tests -v
```

The suite uses real SDK types with a **mocked runtime**. It covers final
messages/cleanup, parameter and path limits, real typed-tool invocation,
agent selection, read/MCP correlation, focus validation and fallback,
permission denials/approvals, and sandbox evidence negative controls.
It makes no model, MCP, authentication, shell-command, or sandbox-backend
calls. Disposable fixtures stay under this repository and are cleaned up.

Walkthrough transcripts are explicitly **illustrative expected output**,
not claims of observed live runs. Offline tests cannot establish model
behavior, cold-resume recall, remote issue access, or OS sandbox enforcement.

Source references target the official
[SDK v1.0.13 tree](https://github.com/github/copilot-sdk/tree/v1.0.13).
Use the installed pinned types when prose and signatures disagree.
A metadata-only check of this host's pinned runtime confirmed that `grep`
supports `output_mode="content"` and otherwise defaults to filenames.
That observation does not explain missing Linux results, prove redaction,
or verify bypass. 08 requires the actual private note in a correlated result.

07 inspects runtime `ask_user` metadata before requesting a structured form.
If that capability is absent, it explicitly creates a legacy freeform
session and validates the same two allowed focus values. Accepting an SDK
option alone does not prove the corresponding runtime tool exists.
