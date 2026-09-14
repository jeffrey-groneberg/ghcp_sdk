# 08 · Sandbox and controlled bypass

📖 **Sources (SDK v1.0.13):**
[official sandbox-bypass E2E](https://github.com/github/copilot-sdk/blob/v1.0.13/nodejs/test/e2e/sandbox_bypass.e2e.test.ts),
[generated Python sandbox types](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/generated/rpc.py),
[1.0.13 release notes](https://github.com/github/copilot-sdk/releases/tag/v1.0.13).

Open [the runnable source](08_sandbox.py). This is a Python port of the
official Node.js E2E pattern: create disposable data, deny one directory in
the runtime sandbox, then require a human decision before one `grep` call may
run outside that sandbox.

The sandbox API is marked **experimental** in 1.0.13. Treat its types and
backend behavior as version-sensitive.

On Linux, the runtime needs an available sandbox backend. The repository's
Debian-based dev container installs `bubblewrap`; without it, the tool call
fails before a bypass can be requested and reports that Bubblewrap is
unavailable. Rebuild an existing Codespace after changing the dev container.

## The flow

```mermaid
sequenceDiagram
    participant App
    participant Runtime
    participant Sandbox
    participant Human
    App->>App: Create temporary workspace/vault marker
    App->>Runtime: create_session(only grep)
    App->>Runtime: options.update(SandboxConfig)
    Runtime->>Sandbox: Deny vault; deny network; allow bypass requests
    App->>Runtime: Ask grep to search denied vault
    Runtime->>Sandbox: Attempt read
    Sandbox-->>Runtime: Blocked by policy
    Runtime->>App: PermissionRequestRead(requestSandboxBypass=true)
    App->>Human: Show reason and exact path
    Human-->>App: Approve once or reject
    App-->>Runtime: ApproveOnce / Reject
    Runtime->>Sandbox: Run this call outside sandbox only if approved
    Runtime-->>App: Tool result and final answer
```

## Code walkthrough

### 1. Enable the release's sandbox feature without dropping the environment

The official E2E enables the `SANDBOX` feature flag. The Python sample copies
the current process environment, preserves existing feature flags, and adds
`SANDBOX`:

```python
env = os.environ.copy()
...
env["COPILOT_CLI_ENABLED_FEATURE_FLAGS"] = ",".join(sorted(flags))
CopilotClient(env=env)
```

Passing only one environment variable would replace the runtime's complete
environment, including `PATH` and authentication-related variables. Preserve
the inherited environment unless deliberate isolation requires otherwise.

### 2. Apply the mutable sandbox configuration

The high-level Python `create_session` signature does not expose a sandbox
argument in 1.0.13. Configure it through the generated experimental RPC after
session creation:

```python
updated = await session.rpc.options.update(
    SessionUpdateOptionsParams(
        sandbox_config=SandboxConfig(
            enabled=True,
            allow_bypass=True,
            add_current_working_directory=True,
            user_policy=SandboxConfigUserPolicy(
                filesystem=SandboxConfigUserPolicyFilesystem(
                    denied_paths=[str(vault)],
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

The current working directory remains usable, the nested demo vault is denied,
and outbound plus loopback network access is disabled. The sample stops if the
runtime rejects the patch.

`allow_bypass=True` does **not** auto-bypass anything. It merely permits the
runtime to ask the host whether one blocked operation may run outside the
sandbox. Omitting the field is fail-closed.

### 3. Keep the non-sandbox permission scope narrow

The session exposes only:

```python
available_tools=ToolSet().add_builtin("grep")
```

The permission handler accepts only `PermissionRequestRead` paths inside the
disposable vault. Ordinary read approval and sandbox enforcement remain
separate checks. An out-of-scope path or permission kind is rejected.

### 4. Recognize and isolate the bypass decision

Sandbox-capable permission requests can include:

- `request_sandbox_bypass=True`;
- `request_sandbox_bypass_reason`;
- the exact requested path.

The sample displays that information, asks once, and returns
`PermissionDecisionApproveOnce()` only for `y`. A second bypass request is
rejected. Timeout/EOF returns `PermissionDecisionUserNotAvailable()`.

Once approved, that individual call runs **outside the sandbox**. The sample
uses only a temporary marker file so the consequence is observable without
exposing real user data.

The `ToolExecutionCompleteData.sandboxed` telemetry field may still report
`True` for a call associated with an enabled sandbox session. Do not use that
single field as bypass proof; correlate the explicit
`request_sandbox_bypass=True` permission request with the successful access to
the otherwise denied marker.

### 5. Understand the boundary

This sandbox constrains runtime-launched tools and processes. It is not a VM,
container, tenant boundary, or authorization system. In particular:

- Python custom-tool handlers run in the host Python process unless the
  application isolates them separately.
- A bypass intentionally removes the sandbox for one approved operation.
- Tool allowlists and permission callbacks are still required.
- Credential injection (`SandboxConfigAuth`) is opt-in and omitted here.
- Backend availability and enforcement details vary by OS; the official E2E
  currently runs only where its macOS sandbox backend is available.

For multi-tenant services, combine sandboxing with isolated workspaces,
per-tenant storage/credentials, process or container isolation, and
application-level authorization.

## Run it

```bash
python examples/08_sandbox.py
```

Verify the Linux backend first when running outside this repository's dev
container:

```bash
command -v bwrap
```

Approve the one disposable-data bypass to exercise the full path:

```text
[tool] grep started

[sandbox bypass] <runtime reason>
Target: /tmp/.../vault
Run this one grep outside the sandbox? [y/N]: y
[tool] completed success=True sandboxed=<runtime-reported>

[agent] SANDBOX_BYPASS_APPROVED
```

Choosing anything other than `y` keeps the vault blocked. The assistant should
report `SANDBOX_BLOCKED`.

## Try this next

1. Keep `allow_bypass` omitted and verify the denied path stays inaccessible.
2. Add a separate read-only directory while leaving the vault denied.
3. Test backend availability on each deployment OS before relying on it.
4. Run a custom Python tool and observe that host-side handlers need their own
   isolation strategy.

## Common pitfalls

- Calling a tool allowlist a sandbox.
- Enabling bypass without a dedicated approval UI and audit trail.
- Assuming a Linux host already provides Bubblewrap or another sandbox backend.
- Passing a partial `env` mapping and accidentally removing runtime settings.
- Assuming a sandbox contains host-side Python callbacks.
- Treating experimental generated types as a permanent compatibility contract.
