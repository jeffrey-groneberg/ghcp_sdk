# Examples: how to run them

Microsoft Copilot SDK 2.0.1 (formerly GitHub Copilot SDK), runtime 1.0.114,
Python 3.11 or later. Setup and sign-in are in the [main README](../README.md).

Run every command from the repository root. Each numbered file stands alone,
and its `.md` file walks through the code.

## Run the code from the slides

The slides show the core of each program. The files add the imports,
`asyncio.run`, a demo repository or a temporary folder where needed, and
printing.

| Slide | Topic | Run | What you see |
|---|---|---|---|
| 17 | First app | `python examples/01_simple_chat.py` | One sentence on what an agent harness is |
| 18 | Events | `python examples/09_events.py` | `[tool] glob started`, `[tool] view started`, then the streamed answer: `add(a, b)` returns `a - b` |
| 19 | Custom tool | `python examples/02_custom_tools.py` | Build 4711 failed: `test_login` hit a `TimeoutError` after 30 s |
| 20 | MCP servers | `python examples/05_mcp_servers.py` | `[mcp] github/list_issues`, then the three newest open enhancement issues in microsoft/copilot-sdk |
| 21 | Custom agents | `python examples/03_custom_agents.py` | The reviewer finds the bug, the fixer fixes it, and the diff shows `return a + b` |
| 24 | Identity | `python examples/10_identity.py` | `runtime signed in: False · session signed in: True (token)`, then `Tool 'bash' does not exist.` |
| 25 | Durable sessions | `python examples/06_session_resume.py create team-assistant-01`, then `resume team-assistant-01` | `OK`, then, from a new process, `AMBER-4711` |
| 25 | sessionFs | `python examples/14_session_fs.py create`, then `resume` | The same, with the journal only in your own store |
| 29 | Connections | `python examples/11_connections.py inprocess`, `stdio` or `server` | `inprocess: 1.0.114, protocol 4`, and so on |
| 30 | Billing | `python examples/15_cost.py` | The tokens and AI credits of each model call, then the session's total |
| 32 | Approval in code | `python examples/12_approval.py` | Run 1: the hook denies `rm -rf build`. Run 2: `rm -r -f build` passes the hook and the approval rejects it |
| 33 | Containment | `python examples/13_containment.py`, then add `--no-sandbox` | `Operation not permitted` (on Linux: `No such file or directory`) and `Could not resolve host`, then `[host] the secret reached the agent: False`; the control run prints `True` |

## More examples

| # | Topic | Run | What you see |
|---|---|---|---|
| 04 | Hooks | `python examples/04_hooks.py` | `[pre] glob` and `[post] glob` around the tool call |
| 07 | Human in the loop | `python examples/07_human_in_the_loop.py` | The agent asks your name, then asks to run one command; `y` writes `greeting.txt` |
| 08 | Sandbox bypass | `python examples/08_sandbox.py` | The runtime asks to run one `grep` outside the sandbox; `y` finds the marker |
| 16 | Skills | `python examples/16_skills.py` | `[skill] pr-description invoked`, then a description in the skill's format |
| | Your own model | `python examples/azure_foundry_byok.py` | The answer from your Microsoft Foundry deployment; set `FOUNDRY_MODEL_URL`, `FOUNDRY_API_KEY` and `FOUNDRY_MODEL` first |

The model's wording differs from run to run.

## Start a runtime server for example 11

The SDK caches the matching runtime, which includes `copilot-runtime`. Start it
in one terminal and keep it running:

```bash
RUNTIME=$(python -m copilot download-runtime | sed -n 's/^Runtime cached at: //p')
"$RUNTIME" --server --port 4321      # prints: CLI server listening on port 4321
```

Then run `python examples/11_connections.py server` in a second terminal. On
Windows, run `python -m copilot download-runtime` and start the
`copilot-runtime.exe` it names. The server signs in the same way as the
examples and listens only on 127.0.0.1; to serve other hosts, see
[backend services](https://github.com/microsoft/copilot-sdk/blob/v2.0.1/docs/setup/backend-services.md).

## Conventions

- **Mode**: `coding-agent` gives one user CLI-like tools; `empty` (examples 10
  and 14) turns off the host's tools and files for multi-user services, and
  each session names the tools it may use.
- **Tools**: every session sets `tools.available_tools`; `[]` means none.
- **Approval**: without `permissions.on_request`, a permission request stays
  pending, so those examples use only tools that need no approval.
  `PermissionHandler.approve_all` approves everything; it's used only where
  that's safe.
- **Cleanup**: leaving `async with CopilotClient(...)` stops the client and
  detaches its sessions. Their journals stay, which is why example 06 can
  resume. Example 14 detaches its session first, because the journal writes
  go through its own storage.
- **Waiting**: `send_and_wait(..., timeout=...)` raises `TimeoutError` when
  the time is up and returns `None` when the session went idle without an
  answer; the examples then print `no answer`.
- **Models**: the examples use the runtime's default model, which was
  `claude-sonnet-5.5` in our runs. `await client.list_models()` lists yours.

## Offline tests

```bash
python -m unittest discover -s examples/tests -v
```

No sign-in, runtime or model call is needed; see the
[main README](../README.md#offline-tests).
