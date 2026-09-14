# GitHub Copilot SDK — an introduction

Build a read-only repository assistant through eight independently runnable
Python checkpoints. The common task is to review this workshop repository,
especially `examples/01_simple_chat.py`, for error handling and cleanup.
The examples use **`github-copilot-sdk==1.0.13`**, the stable release verified on
**2026-09-14**. Both dependency manifests pin it.

Start with a streamed plan from supplied context, add a typed repository tool,
select a reviewer, observe tool execution, fetch issue context, resume a review,
and compare rejected versus approved operations. These are focused checkpoints
of the same use case, not a cumulative production application.

**Baseline:** Python **3.11+** (3.12 recommended), Pydantic **2+**, and the
SDK release's Copilot CLI/runtime **1.0.83**. Like the official Python samples,
these examples use the runtime-selected default model; availability and billing
depend on your account, organization and plan.

Sources: [PyPI 1.0.13](https://pypi.org/project/github-copilot-sdk/1.0.13/),
[release v1.0.13 — September 4, 2026](https://github.com/github/copilot-sdk/releases/tag/v1.0.13),
[tagged runtime pin](https://github.com/github/copilot-sdk/blob/v1.0.13/nodejs/package.json).
Walkthrough links target **v1.0.13**, not unreleased `main`. Where upstream
prose is stale, the tagged Python implementation is the authority.
The implementation style follows the official
[`python/samples`](https://github.com/github/copilot-sdk/tree/v1.0.13/python/samples)
and version-pinned types and tests.

## What the SDK adds

A direct model API returns text or proposed tool calls. Your application must
then dispatch tools, return their results, and repeat model calls. With the
Copilot SDK, the **runtime** manages that loop and conversation state; the SDK
transports requests and exposes events, tool registration, and host callbacks.
Your application still authorizes access and supplies credentials.

For one repository-inspection request:

1. The application sends a prompt through `session.send_and_wait`.
2. The runtime sends context and tool schemas to the model.
3. The model proposes `inspect_python_file` with a file argument.
4. The runtime asks the host for permission. Rejection skips execution.
5. On approval, the custom host handler validates the allowed file and returns
   AST metadata.
6. The runtime passes that result back to the model for another iteration.
7. A final assistant message and idle event complete the wait.

Built-in tools execute in the runtime; custom Python handlers execute in the
host process. One user request can cause several model calls. In SDK event
terminology, `assistant.turn_start` describes an individual model iteration.

<details>
<summary>Release details since the original SDK 1.0.0 workshop (optional)</summary>

| Stable addition | What it means here |
|---|---|
| [1.0.13: client identity](https://github.com/github/copilot-sdk/blob/v1.0.13/docs/features/client-info.md) | Example 01 sends `client_info` with application/integration names and versions on `server.connect`. This changes telemetry attribution, not authentication or what telemetry is collected. |
| [1.0.13: selectable `ask_user`](https://github.com/github/copilot-sdk/releases/tag/v1.0.13) | Example 07 prefers `ask_user_variant="elicitation"`, verifies that `ask_user` actually appears in runtime tool metadata, and falls back to a narrowly validated legacy callback when the bundled runtime does not expose the structured tool. |
| [1.0.13: rotating session credentials](https://github.com/github/copilot-sdk/releases/tag/v1.0.13) | `github_token_provider` handles initial acquisition and refresh; mutually exclusive with a static per-session `github_token`. A `kind="token"` result requires positive `expiresIn` **seconds remaining**; `kind="cancelled"` is the cancellation alternative. Initial errors/cancellation reject create/resume, not fall back to ambient auth. Generic MCP connections still own their separate authentication flow. |
| [1.0.13: external tool cancellation](https://github.com/github/copilot-sdk/releases/tag/v1.0.13) | Python async tool handler tasks are cancelled when their runtime request completes or their session terminates. Let `asyncio.CancelledError` propagate; clean up resources with `finally` / context managers. |
| [1.0.13: detach cleanup](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/session.py) | Session exit calls `disconnect()` → `session.detach`, preserving persisted state and other owners. Use `client.delete_session(id)` only for explicit deletion. |
| [Runtime connection configuration](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/client.py) | Use `connection=RuntimeConnection.for_stdio(path=...)` for an explicit executable or `RuntimeConnection.for_uri(...)` for an existing server. Legacy `cli_path` / `cli_url` client keywords are not accepted by the pinned Python API. |
| [1.0.13: managed policy and Auto tiers](https://github.com/github/copilot-sdk/releases/tag/v1.0.13) | `managed_settings` injects permissions only, requires CLI **1.0.79-5+**, composes restrictively, and must be re-supplied on resume. `set_auto_tier("efficiency")` stages an Auto preference, committed on the next successful `auto` turn; these examples follow the runtime default model. |
| [1.0.13: sandbox bypass](https://github.com/github/copilot-sdk/blob/v1.0.13/nodejs/test/e2e/sandbox_bypass.e2e.test.ts) | Example 08 ports the official E2E pattern to Python: enable `SandboxConfig`, deny a disposable path, and require a fresh human decision before one tool call may run outside the sandbox. The API is experimental. |
| [1.0.9](https://github.com/github/copilot-sdk/releases/tag/v1.0.9) / [1.0.11](https://github.com/github/copilot-sdk/releases/tag/v1.0.11) | Earlier stable fixes include JSON-mode Pydantic tool results, source-qualified tool filtering documentation, `on_agent_stop`, clearer permission types, `Tool.is_terminal`, and history clear/rewind APIs. No experimental factory features are needed by these demos. |

</details>

## Open in Codespaces

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/jeffrey-groneberg/ghcp_sdk?quickstart=1)

The devcontainer provides Python 3.12, GitHub CLI, Bubblewrap, and the pinned
Python dependencies. The SDK downloads its matching runtime on first use;
it does **not** install the interactive `copilot` command on your PATH.
Follow the authentication setup below, then run:

```bash
python examples/01_simple_chat.py
```

## Local setup and authentication

The eight supplied scripts use GitHub-hosted Copilot models. They need:

- **Python 3.11+** and network access for GitHub/PyPI/runtime downloads.
- A GitHub account with **Copilot access**, an eligible model and sufficient
  quota. Organization policy can restrict SDK/CLI or model access.
- For interactive sign-in, separately
  [install the Copilot CLI](https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli)
  and run `copilot login`; alternatively provision `COPILOT_GITHUB_TOKEN`
  securely through your environment. Never paste tokens into source or logs.
- Example 05 separately needs a GitHub token accepted by the remote GitHub MCP
  server. It resolves `GITHUB_TOKEN`, `GH_TOKEN`, then `gh auth token` at run
  time and never logs the value. Copilot CLI sign-in authenticates the model
  runtime but is not automatically copied into a generic MCP connection.
  **No Node.js, `npx`, Docker, or local MCP server is required.**

```bash
git clone https://github.com/jeffrey-groneberg/ghcp_sdk.git
cd ghcp_sdk
python3.12 -m venv .venv
source .venv/bin/activate             # macOS / Linux
# .venv\Scripts\Activate.ps1          # Windows PowerShell
python -m pip install \
  --index-url https://packagefeedproxy.microsoft.io/pypi/simple \
  -r requirements.txt
python -c "import importlib.metadata as m; print(m.version('github-copilot-sdk'))"
# Optional: pre-download the release-matched runtime before the workshop.
python -m copilot download-runtime
```

Use another installed Python **3.11+** interpreter if `python3.12` is absent.
The normal SDK path provisions runtime **1.0.83** automatically. An explicit
`RuntimeConnection.for_stdio(path=...)` or `COPILOT_CLI_PATH` overrides that
selection; keep overrides version-compatible rather than silently using an
old CLI. See [tagged runtime setup](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/_cli_download.py).

**Package feeds:** Python installation uses
`https://packagefeedproxy.microsoft.io/pypi/simple`; the devcontainer exports
the same URL as `PIP_INDEX_URL`. Optional npm tooling continues to use
`https://packagefeedproxy.microsoft.io/npm/`. None of the eight Python
examples requires npm.

**Windows:** set `$env:PYTHONIOENCODING = "utf-8"` in PowerShell before running.
Examples 07 and 08 require an interactive terminal; human prompts expire after
120 seconds.

### Optional BYOK authentication

The pinned SDK also supports provider `api_key`, `bearer_token`, and
**`bearer_token_provider`** authentication. The callback can acquire fresh
Microsoft Entra tokens on demand, including managed identity for supported
**Microsoft Foundry** endpoints. This is separate from the session's
GitHub credential callback and from authentication for generic MCP servers.

Follow the tagged [BYOK guide](https://github.com/github/copilot-sdk/blob/v1.0.13/docs/auth/byok.md)
and [Azure managed identity guide](https://github.com/github/copilot-sdk/blob/v1.0.13/docs/setup/azure-managed-identity.md)
for provider configuration, Azure permissions and optional Azure Identity
dependencies; those dependencies are not required by these eight examples.
BYOK is **not** an automatic air-gap or “no GitHub traffic” guarantee:
review runtime provisioning, authentication, telemetry and other enabled
services for your deployment. Prefer these dedicated guides and tagged
Python types over stale upstream “key-only” summaries.

## Examples

Read each walkthrough, then run its `.py` file **from the repository root**.
Choose a different available model via `await client.list_models()` rather
than assuming that a newly announced model is available to your account.

| # | Walkthrough | Python | Capability |
|---|---|---|---|
| 1 | [Streaming chat](examples/01_simple_chat.md) | [Source](examples/01_simple_chat.py) | Stream a review plan from supplied context; no file tools yet |
| 2 | [Custom tools](examples/02_custom_tools.md) | [Source](examples/02_custom_tools.py) | Pydantic input and validated AST metadata for an allowed Python file |
| 3 | [Custom agents](examples/03_custom_agents.md) | [Source](examples/03_custom_agents.py) | Research the repository, then select and verify its reviewer |
| 4 | [Hooks](examples/04_hooks.md) | [Source](examples/04_hooks.py) | Observe repository reads through pre-call, success, and failure hooks |
| 5 | [Remote GitHub MCP](examples/05_mcp_servers.md) | [Source](examples/05_mcp_servers.py) | Read this repository's current issues; separate authentication and result evidence |
| 6 | [Session persistence](examples/06_session_resume.md) | [Source](examples/06_session_resume.py) | Persist a review file and focus, then recall them in a new process |
| 7 | [Human in the loop](examples/07_human_in_the_loop.md) | [Source](examples/07_human_in_the_loop.py) | Validate the review focus, then approve or reject the fixed test command |
| 8 | [Sandbox bypass](examples/08_sandbox.md) | [Source](examples/08_sandbox.py) | Deny a disposable private review note; separately approve one read |

### What Example 08 is testing

The sandbox example is not trying to prove that an AI can read a file. It is
testing whether a runtime-launched tool can be **contained, blocked, escalated,
approved once, and independently verified**.

The script creates a temporary workspace containing a nested `vault` with a
disposable private review note. Its unpredictable marker is not given to the
model in the prompt. It then:

1. exposes only the built-in `grep` tool;
2. keeps the workspace available while explicitly denying the nested vault;
3. denies outbound and local network access;
4. allows the runtime to request a sandbox bypass, but does not grant one
   automatically;
5. asks `grep` to search the denied vault and return matching content.

The first access attempt is therefore expected to hit the sandbox policy. The
runtime sends the host a `PermissionRequestRead` with
`request_sandbox_bypass=True`. The host displays the exact path and asks the
human for a fresh decision. Only `y` returns `ApproveOnce`, allowing that one
tool call to run outside the sandbox. A rejection, timeout, EOF, unexpected
permission type, out-of-scope path, or second bypass request fails closed.

The final verdict comes from the application, not from the model. The host
requires recorded approval and a matching successful tool result containing
the private note. `success=True` is insufficient: a search may complete but
return filenames or no matching lines. Missing content is not assumed to be
platform-specific redaction and is not accepted as proof.

The completion event may still report `sandboxed=True` during a bypass flow.
That field alone does not establish whether the note was read or permission
was granted. A missing backend, missing note content, or unmatched tool result
must remain an explicit failure rather than a successful demonstration.

This separation matters because each control answers a different security
question:

| Control | Question it answers |
|---|---|
| `ToolSet().add_builtin("grep")` | Which capability can the agent attempt to use? |
| Permission callback | Does the application authorize this exact request? |
| `SandboxConfig` | What can the runtime process reach even after a tool is authorized? |
| Human-approved bypass | May this one blocked operation cross the containment boundary? |
| Correlated tool events and note content | Did the approved read actually return the private note? |

This is defense in depth against prompt injection, incorrect model decisions,
and overly broad tool arguments. A tool allowlist is not a sandbox, and a
sandbox is not application authorization.

The API remains experimental in SDK 1.0.13. The Linux Codespace uses
Bubblewrap; other platforms can use different backends or provide none.
Runtime sandboxing also does not automatically contain Python custom-tool
handlers running in the host process. Production multi-user systems still need
isolated workspaces, per-user credentials and authorization, process or
container boundaries, audit logs, and a deliberately designed approval UI.
See the [complete sandbox walkthrough](examples/08_sandbox.md) for the event
flow, code, limitations, and expected output.

```bash
python examples/01_simple_chat.py
python examples/02_custom_tools.py
python examples/03_custom_agents.py
python examples/04_hooks.py
python examples/05_mcp_servers.py
python examples/06_session_resume.py
python examples/06_session_resume.py --resume
python examples/07_human_in_the_loop.py
python examples/08_sandbox.py
```

**Safety and failures:** `approve_all` is only for trusted demonstrations.
Read tools can expose sensitive files; prompts and tool filters are not an
OS sandbox or a complete authorization system. Example 07 validates an exact
command before asking the user. Example 08 uses the runtime's experimental OS
sandbox, but an approved bypass intentionally executes one call outside it.
Runtime/transport errors remain visible. `send_and_wait`
raises `TimeoutError` (default 60 seconds); `None` means idle without a final
assistant message, not timeout. A wait timeout does **not** itself abort
in-flight work; these scripts exit their owned client, while long-lived apps
should implement cancellation/`session.abort()` deliberately.

### Offline validation (no model calls)

```bash
python -m unittest discover -s examples/tests -v
```

Focused stdlib tests exercise all eight samples, callbacks, tool schema/results, lifecycle,
error/timeout handling, agent selection, token lookup and both resume paths
using mocks. They do not prove live model, MCP or authentication behavior.

## Slides

- [`docs/index.html`](docs/index.html): custom **scroll-snap HTML** workshop
  deck (not reveal.js). Open in a browser or serve the `docs/` folder.
- [`GitHub-Copilot-SDK.pptx`](GitHub-Copilot-SDK.pptx): the matching PowerPoint deck.

Both contain **18 introduction slides and 4 optional appendix slides**. The
introduction retains four chapters: SDK in detail, SDK vs. CLI, capabilities,
and samples. Runtime deployment, multi-user hosting, authentication variants,
and BYOK are deferred until after the exercises and discussion.

The HTML hides the appendix by default. Use **Show optional appendix** on the
references slide, add `?appendix=1` to the URL, or follow an appendix fragment
such as `#appendix-byok`. In PowerPoint the appendix slides are marked hidden
for normal slide shows and remain accessible in the editor.

The narrative is maintained once in [`docs/deck.json`](docs/deck.json).
The builder extracts teaching snippets directly from the executable Python
files. Missing or ambiguous snippet boundaries fail the build, rather than
silently retaining an outdated code example. Both formats use those same
excerpts. Approval traces are explicitly labelled illustrative paths, not
fabricated recordings or guarantees of model wording.

```bash
python -m http.server -d docs 8000
# http://localhost:8000
```

To change the deck, edit `docs/deck.json`; edit `docs/index.html` only for its
styles and navigation, outside the generated-slide markers. Regenerate both
formats in a separate tooling environment:

```bash
python3 -m venv .venv-slides
source .venv-slides/bin/activate
python -m pip install -r scripts/requirements-slides.txt
python scripts/build_slides.py
```

The offline checks require only the Python standard library:

```bash
python scripts/build_slides.py --check
python -m unittest discover -s scripts/tests -v
```

The Pages workflow runs these checks before publishing. It rejects a stale
deck, mismatched code excerpt, missing final-message check, unchecked agent
selection, placeholder MCP header, or incorrectly exposed appendix.

## References

- [Python README at v1.0.13](https://github.com/github/copilot-sdk/blob/v1.0.13/python/README.md)
- [Tagged Python client](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/client.py),
  [session](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/session.py),
  [tools](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/tools.py)
- [Authentication](https://github.com/github/copilot-sdk/blob/v1.0.13/docs/auth/authenticate.md)
  and [BYOK](https://github.com/github/copilot-sdk/blob/v1.0.13/docs/auth/byok.md)
- [GitHub MCP server v1.12.1](https://github.com/github/github-mcp-server/tree/v1.12.1)
  and [MCP specification](https://modelcontextprotocol.io/)
- [All SDK releases](https://github.com/github/copilot-sdk/releases)

## License

[MIT](LICENSE)
