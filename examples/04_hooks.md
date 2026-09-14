# 04 · Observe a source read with hooks

**GitHub Copilot SDK - an introduction**

[Runnable source](04_hooks.py) · [Student guide](README.md)

**Sources, SDK v1.0.13:** [Python hook types and dispatch](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/session.py),
[hook overview](https://github.com/github/copilot-sdk/blob/v1.0.13/docs/features/hooks.md),
[pre-tool contract](https://github.com/github/copilot-sdk/blob/v1.0.13/docs/hooks/pre-tool-use.md).

## Goal and boundary

Observe the runtime reading `examples/01_simple_chat.py`, then explaining
its error handling and subscription cleanup. The session starts in this
repository root and exposes only `view`.

**These callbacks log; they do not enforce policy.** Returning `None` leaves
normal permission handling unchanged. This example is not a sandbox.

```mermaid
sequenceDiagram
    participant Host
    participant Runtime
    Host->>Runtime: Request view of the exact target file
    Runtime->>Host: on_pre_tool_use(toolName, toolArgs)
    Host-->>Runtime: None; log the tool name
    Runtime->>Runtime: Permission handling and tool execution
    alt Successful tool result
        Runtime->>Host: on_post_tool_use
    else Failed tool result
        Runtime->>Host: on_post_tool_use_failure(error)
    end
    Runtime-->>Host: Correlated start/completion events + final message
    Host->>Host: Require a successful view result for this file
```

## Important code

```python
hooks={
    "on_pre_tool_use": on_pre_tool_use,
    "on_post_tool_use": on_post_tool_use,
    "on_post_tool_use_failure": on_post_tool_use_failure,
},
```

- The pre-hook logs `[pre]  view`.
- The success hook logs `[post] view succeeded`.
- The failure hook logs `[failed] view: <error>` to stderr.
- None prints source payloads or changes the request/result.

The tagged Python hook input uses `sessionId`, `timestamp`,
`workingDirectory`, `toolName`, and `toolArgs`. The success hook additionally
receives `toolResult`; the failure hook receives `error`. The separate
invocation context contains `session_id`. These pre/post hook types do
**not** expose `toolCallId` in 1.0.13.

For correlation, the example therefore separately observes actual
`ToolExecutionStartData` and `ToolExecutionCompleteData` events with
`_tool_trace.ToolTrace`. It requires:

1. a `view` start with `arguments["path"] == str(REVIEW_PATH)`;
2. a successful completion with the **same `tool_call_id`**;
3. a nonempty result and the required final assistant message.

```python
if not any(
    is_review_read(start) and trace.successful_content(call_id)
    for call_id, start in trace.started.items()
):
    raise RuntimeError("No matching successful view result for the review file.")
```

The host prints `READ_VERIFIED` only after those checks. A directory listing,
unrelated file, failed result, missing result, or unmatched completion is
not accepted. This proves an observed scoped read, not review accuracy.

Other hooks can return documented `permissionDecision` values or
`modifiedArgs`, but this example deliberately does neither. See 07/08 for
narrow application checks; do not describe a printing hook as enforcement.

## Run and inspect

```bash
python examples/04_hooks.py
```

**Illustrative success trace, not an observed run:**

```text
[pre]  view
[post] view succeeded
[host] READ_VERIFIED file=examples/01_simple_chat.py
<Assistant explains source-cited error handling and cleanup.>
```

**Illustrative failure trace:**

```text
[pre]  view
[failed] view: <runtime failure message>
RuntimeError: No matching successful view result for the review file.
```

The success hook does not run for failed tool results. Listener cleanup is
in `finally`; the final message, 120-second turn deadline, and 180-second
outer deadline are independent of hook logging.

**Exercise:** mock a successful completion with a different call ID. Seeing
both a start and a success somewhere in the log must not satisfy the check.
