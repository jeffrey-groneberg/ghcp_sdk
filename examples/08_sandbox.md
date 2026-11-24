# 08 · Sandbox bypass

[Source](08_sandbox.py) · [SandboxConfig and its policy types](https://github.com/microsoft/copilot-sdk/blob/v2.0.1/python/copilot/_generated/rpc.py)

The runtime sandbox denies a disposable vault folder. When `grep` tries to
search it, the runtime asks your code whether this one call may run outside the
sandbox, and only your `y` lets it.

## Run it

```bash
python examples/08_sandbox.py
```

## How it works

```python
sandbox = SandboxConfig(
    enabled=True, add_current_working_directory=True,
    allow_bypass=True,  # the runtime may ask to run one call outside
    user_policy=SandboxConfigUserPolicy(
        filesystem=SandboxConfigUserPolicyFilesystem(denied_paths=[str(vault)]),
        network=SandboxConfigUserPolicyNetwork(allow_outbound=False,
                                               allow_local_network=False)))
session = await client.create_session(
    working_directory=workspace,
    tools={"available_tools": ["builtin:grep"]},
    permissions={"on_request": on_permission, "sandbox": sandbox}, ...)
```

- `permissions.sandbox` turns the sandbox on when the session starts. The
  policy denies the vault and all network access.
- `allow_bypass=True` lets the runtime ask for an exception. That request
  reaches `on_permission` with `request_sandbox_bypass=True`; other requests
  are approved and run inside the sandbox.
- The tool events show what happened: after `y`, `success=True` with the
  marker found; after `n`, `success=False`.
- `SandboxConfig` and its policy types are experimental in SDK 2.0.1. No
  feature flag was needed in our runs. Example 13 shows the sandbox without a
  bypass.

## Output from a live run

```text
[sandbox bypass] /tmp/tmp.../vault
Run this one call outside the sandbox? [y/N] y
[tool] success=True sandboxed=True marker found=True

Found. The text `OUTSIDE_MATCH_LINE sandbox-bypass-approved` appears on line 1 of `vault/notes.txt`.
```

With `n`: `[tool] success=False sandboxed=True marker found=False`, and the
agent reports that the search didn't run.

## Watch out

- An approved bypass runs that one call outside the sandbox. Show exactly what
  will run, and default to "no".
