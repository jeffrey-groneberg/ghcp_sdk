# 12 · Approval in code

Deck slide 32 · [Source](12_approval.py) · [Pre-tool-use hook](https://github.com/microsoft/copilot-sdk/blob/v2.0.1/docs/hooks/pre-tool-use.md) · [Permission handling](https://github.com/microsoft/copilot-sdk/blob/v2.0.1/python/README.md#permission-handling)

Two checks run before a command: a hook with a block list, then an approval
function that accepts only one exact command.

## Run it

```bash
python examples/12_approval.py
```

The example uses the `bash` tool, so it needs macOS or Linux; a Codespace
works.

## How it works

The code from the slide, which the example extends with prints:

```python
async def pre_tool_use(hook_input, invocation):
    if any(p in str(hook_input["toolArgs"]) for p in ("rm -rf", "sudo")):
        return {"permissionDecision": "deny",
                "permissionDecisionReason": "Blocked by policy"}

def on_permission(request, invocation):
    if getattr(request, "full_command_text", "") == "git status":
        return PermissionDecisionApproveOnce()
    return PermissionDecisionReject(feedback="Not approved in this demo.")
```

- The hook (`hooks.handlers.on_pre_tool_use`) sees every tool call first. The
  approval function (`permissions.on_request`) answers permission requests,
  which the runtime makes only for calls that need approval: `git status` only
  reads, so it runs without one.
- Run 1: `rm -rf build` matches the block list, and the hook denies it.
- Run 2: `rm -r -f build` would delete the same folder but isn't on the list.
  It passes the hook, and the exact match rejects it. A block list misses
  variants; an exact match lets none through.
- `PermissionDecisionApproveOnce` and `PermissionDecisionReject` are
  experimental in SDK 2.0.1.

## Output from a live run

```text
--- run 1
[hook] passed: git status
[hook] denied: rm -rf build
agent: ... `rm -rf build` was denied by a preToolUse hook with the message "Blocked by policy". The `build/` directory was not removed. ...
build/ still there: True
--- run 2
[hook] passed: rm -r -f build
[approval] rejected: rm -r -f build
agent: I ran `rm -r -f build` once, and the tool call was rejected before it executed. The feedback was "Not approved in this demo." ...
build/ still there: True
```
