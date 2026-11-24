# 04 · Hooks

[Source](04_hooks.py) · [Hooks](https://github.com/microsoft/copilot-sdk/blob/v2.0.1/docs/features/hooks.md) · [Pre-tool-use hook](https://github.com/microsoft/copilot-sdk/blob/v2.0.1/docs/hooks/pre-tool-use.md)

Hooks run your code at fixed points of the agent loop. This example traces
every tool call: before it runs, after it succeeds and after it fails.

## Run it

```bash
python examples/04_hooks.py
```

## How it works

```python
hooks={"handlers": {
    "on_pre_tool_use": on_pre_tool_use,
    "on_post_tool_use": on_post_tool_use,
    "on_post_tool_use_failure": on_post_tool_use_failure,
}}
```

- SDK 2.0 takes the hook functions under `hooks.handlers`.
- Each hook gets a dictionary with `toolName`, `toolArgs` and more. Returning
  `None` means "no opinion". A pre-tool hook can also return a
  `permissionDecision` (`"deny"` with a `permissionDecisionReason`, `"allow"`
  or `"ask"`), `modifiedArgs` or `additionalContext`; example 12 denies calls
  this way.
- Other hooks run before MCP tool calls, on prompts, when a session starts or
  ends, on errors, around sub-agents and when the agent stops.

## Output from a live run

```text
[pre]    glob
[post]   glob
Python files in `examples/`:
- 01_simple_chat.py
...
```

## Try this next

- Deny `view` for files outside `examples/` by returning
  `{"permissionDecision": "deny", "permissionDecisionReason": "..."}` from
  `on_pre_tool_use`.
