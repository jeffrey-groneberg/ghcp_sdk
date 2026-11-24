# 13 · Containment

Deck slide 33 · [Source](13_containment.py) · [SandboxConfig and its policy types](https://github.com/microsoft/copilot-sdk/blob/v2.0.1/python/copilot/_generated/rpc.py)

The permission handler approves every request, so only the sandbox can stop a
command. It still blocks reading the vault and reaching the network.

## Run it

```bash
python examples/13_containment.py
python examples/13_containment.py --no-sandbox    # the control run
```

The example uses the `bash` tool, so it needs macOS or Linux; a Codespace
works.

## How it works

```python
files = SandboxConfigUserPolicyFilesystem(denied_paths=[str(vault)])
network = SandboxConfigUserPolicyNetwork(allow_outbound=False,
                                         allow_local_network=False)
policy = SandboxConfigUserPolicy(filesystem=files, network=network)
sandbox = SandboxConfig(enabled=sandbox_on, add_current_working_directory=True,
                        user_policy=policy)               # no allow_bypass
session = await client.create_session(
    working_directory=work,
    tools={"available_tools": ["builtin:bash"]},
    permissions={"on_request": PermissionHandler.approve_all,  # all calls
                 "sandbox": sandbox}, ...)
```

- The session has only `bash`, and `approve_all` approves every call. Without
  `allow_bypass`, nothing runs outside the sandbox.
- The host, not the model, reports whether the secret reached the agent.
- macOS uses its built-in sandbox; Linux uses Bubblewrap. In a dev container
  or Codespace, Bubblewrap needs the `securityOpt` settings in
  [.devcontainer/devcontainer.json](../.devcontainer/devcontainer.json).
- `SandboxConfig` and its policy types are experimental in SDK 2.0.1; no
  feature flag was needed in our runs.

## What the sandbox covers

Shell commands run inside it, and by default so do the local MCP and language
servers the session launches. Built-in file tools are checked against the
policy, best effort. Remote MCP servers are never sandboxed, because they run
elsewhere, but by default the session's traffic to them stays under the
sandbox's network policy (`sandbox_mcp_servers` defaults to true). Your own
tool handlers and the in-process runtime itself are outside the sandbox.

## Output from a live run

```text
$ cat vault/secret.txt
$ curl -sS -m 5 https://github.com
  cat: vault/secret.txt: Operation not permitted
  curl: (6) Could not resolve host: github.com
...
[host] the secret reached the agent: False
```

On Linux, Bubblewrap hides the denied folder, so `cat` reports
`No such file or directory` instead. With `--no-sandbox`, `cat` prints
`TOP-SECRET-MARKER`, `curl` downloads the page, and the host reports `True`.
