# GitHub Copilot SDK — Python workshop

Seven small, self-contained, commented prototypes and walkthroughs for
**`github-copilot-sdk==1.0.13`**, the latest stable PyPI release verified on
**2026-09-07**. Both dependency manifests pin this SDK version.

**Baseline:** Python **3.11+** (3.12 recommended), Pydantic **2+**, and the
SDK release's Copilot CLI/runtime **1.0.83**. Examples use **`gpt-5-mini`**;
availability and billing depend on your account, organization and plan.

Sources: [PyPI 1.0.13](https://pypi.org/project/github-copilot-sdk/1.0.13/),
[release v1.0.13 — September 4, 2026](https://github.com/github/copilot-sdk/releases/tag/v1.0.13),
[tagged runtime pin](https://github.com/github/copilot-sdk/blob/v1.0.13/nodejs/package.json).
Walkthrough links target **v1.0.13**, not unreleased `main`. Where upstream
prose is stale, the tagged Python implementation is the authority.

## What's new since the original 1.0.0 workshop?

| Stable addition | What it means here |
|---|---|
| [1.0.13: client identity](https://github.com/github/copilot-sdk/blob/v1.0.13/docs/features/client-info.md) | Example 01 sends `client_info` with application/integration names and versions on `server.connect`. This changes telemetry attribution, not authentication or what telemetry is collected. |
| [1.0.13: selectable `ask_user`](https://github.com/github/copilot-sdk/releases/tag/v1.0.13) | Example 07 explicitly uses `ask_user_variant="legacy"` (also the default). `"elicitation"` requires an `on_elicitation_request` structured-form handler. |
| [1.0.13: rotating session credentials](https://github.com/github/copilot-sdk/releases/tag/v1.0.13) | `github_token_provider` handles initial acquisition and refresh; mutually exclusive with a static per-session `github_token`. A `kind="token"` result requires positive `expiresIn` **seconds remaining**; `kind="cancelled"` is the cancellation alternative. Initial errors/cancellation reject create/resume, not fall back to ambient auth. This does not rotate example 05's MCP header. |
| [1.0.13: external tool cancellation](https://github.com/github/copilot-sdk/releases/tag/v1.0.13) | Python async tool handler tasks are cancelled when their runtime request completes or their session terminates. Let `asyncio.CancelledError` propagate; clean up resources with `finally` / context managers. |
| [1.0.13: detach cleanup](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/session.py) | Session exit calls `disconnect()` → `session.detach`, preserving persisted state and other owners. Use `client.delete_session(id)` only for explicit deletion. |
| [Runtime connection configuration](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/client.py) | Use `connection=RuntimeConnection.for_stdio(path=...)` for an explicit executable or `RuntimeConnection.for_uri(...)` for an existing server. Legacy `cli_path` / `cli_url` client keywords are not accepted by the pinned Python API. |
| [1.0.13: managed policy and Auto tiers](https://github.com/github/copilot-sdk/releases/tag/v1.0.13) | `managed_settings` injects permissions only, requires CLI **1.0.79-5+**, composes restrictively, and must be re-supplied on resume. `set_auto_tier("efficiency")` stages an Auto preference, committed on the next successful `auto` turn; these examples keep a fixed model. |
| [1.0.9](https://github.com/github/copilot-sdk/releases/tag/v1.0.9) / [1.0.11](https://github.com/github/copilot-sdk/releases/tag/v1.0.11) | Earlier stable fixes include JSON-mode Pydantic tool results, source-qualified tool filtering documentation, `on_agent_stop`, clearer permission types, `Tool.is_terminal`, and history clear/rewind APIs. No experimental factory features are needed by these demos. |

## Open in Codespaces

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/jeffrey-groneberg/ghcp_sdk?quickstart=1)

The devcontainer provides Python 3.12 and GitHub CLI and installs the pinned
Python dependencies. The SDK downloads its matching runtime on first use;
it does **not** install the interactive `copilot` command on your PATH.
Follow the authentication setup below, then run:

```bash
python examples/01_simple_chat.py
```

## Local setup and authentication

The seven supplied scripts use GitHub-hosted Copilot models. They need:

- **Python 3.11+** and network access for GitHub/PyPI/runtime downloads.
- A GitHub account with **Copilot access**, an eligible model and sufficient
  quota. Organization policy can restrict SDK/CLI or model access.
- For interactive sign-in, separately
  [install the Copilot CLI](https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli)
  and run `copilot login`; alternatively provision `COPILOT_GITHUB_TOKEN`
  securely through your environment. Never paste tokens into source or logs.
- Example 05 separately needs credentials accepted by the remote GitHub MCP
  server, with access to the target repository. **No Node.js, `npx`, Docker,
  or local MCP server is required.** `gh` is optional if a token is supplied.

```bash
git clone https://github.com/jeffrey-groneberg/ghcp_sdk.git
cd ghcp_sdk
python3.12 -m venv .venv
source .venv/bin/activate             # macOS / Linux
# .venv\Scripts\Activate.ps1          # Windows PowerShell
python -m pip install -r requirements.txt
python -c "import importlib.metadata as m; print(m.version('github-copilot-sdk'))"
# Optional: pre-download the release-matched runtime before the workshop.
python -m copilot download-runtime
```

Use another installed Python **3.11+** interpreter if `python3.12` is absent.
The normal SDK path provisions runtime **1.0.83** automatically. An explicit
`RuntimeConnection.for_stdio(path=...)` or `COPILOT_CLI_PATH` overrides that
selection; keep overrides version-compatible rather than silently using an
old CLI. See [tagged runtime setup](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/_cli_download.py).

**Optional npm tooling:** the repository `.npmrc` and devcontainer
`NPM_CONFIG_REGISTRY` setting use `https://packagefeedproxy.microsoft.io/npm/`.
This configures npm, not pip; none of the seven Python/HTTP MCP examples
requires npm.

**Windows:** set `$env:PYTHONIOENCODING = "utf-8"` in PowerShell before running.
Example 07 requires an interactive terminal; human prompts expire after 30 seconds.

### Optional BYOK authentication

The pinned SDK also supports provider `api_key`, `bearer_token`, and
**`bearer_token_provider`** authentication. The callback can acquire fresh
Microsoft Entra tokens on demand, including managed identity for supported
**Microsoft Foundry** endpoints. This is separate from the session's
GitHub credential callback and from example 05's MCP authorization header.

Follow the tagged [BYOK guide](https://github.com/github/copilot-sdk/blob/v1.0.13/docs/auth/byok.md)
and [Azure managed identity guide](https://github.com/github/copilot-sdk/blob/v1.0.13/docs/setup/azure-managed-identity.md)
for provider configuration, Azure permissions and optional Azure Identity
dependencies; those dependencies are not required by these seven examples.
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
| 1 | [Streaming chat](examples/01_simple_chat.md) | [Source](examples/01_simple_chat.py) | Client identity, streaming events, bounded waiting and lifecycle |
| 2 | [Custom tools](examples/02_custom_tools.md) | [Source](examples/02_custom_tools.py) | `@define_tool`, Pydantic schema, explicitly fictional weather |
| 3 | [Custom agents](examples/03_custom_agents.md) | [Source](examples/03_custom_agents.py) | Researcher → reviewer, typed RPC selection and verification |
| 4 | [Hooks](examples/04_hooks.md) | [Source](examples/04_hooks.py) | Pre-tool, successful-result and failed-result callbacks without logging sensitive arguments |
| 5 | [Remote GitHub MCP](examples/05_mcp_servers.md) | [Source](examples/05_mcp_servers.py) | HTTP transport, run-time credentials, read-only issue tools |
| 6 | [Session persistence](examples/06_session_resume.md) | [Source](examples/06_session_resume.py) | Create, detach, resume and stable/discoverable session IDs |
| 7 | [Human in the loop](examples/07_human_in_the_loop.md) | [Source](examples/07_human_in_the_loop.py) | Permission decisions and bounded legacy `ask_user` input |

```bash
python examples/01_simple_chat.py
python examples/02_custom_tools.py
python examples/03_custom_agents.py
python examples/04_hooks.py
python examples/05_mcp_servers.py
python examples/06_session_resume.py
python examples/06_session_resume.py --resume
python examples/07_human_in_the_loop.py
```

**Safety and failures:** `approve_all` is only for trusted demonstrations.
Read tools can expose sensitive files; prompts and tool filters are not an
OS sandbox or a complete authorization system. Inspect commands before
approving example 07. Runtime/transport errors remain visible. `send_and_wait`
raises `TimeoutError` (default 60 seconds); `None` means idle without a final
assistant message, not timeout. A wait timeout does **not** itself abort
in-flight work; these scripts exit their owned client, while long-lived apps
should implement cancellation/`session.abort()` deliberately.

### Offline validation (no model calls)

```bash
python -m unittest discover -s examples/tests -v
```

Focused stdlib tests exercise callbacks, tool schema/results, lifecycle,
error/timeout handling, agent selection, token lookup and both resume paths
using mocks. They do not prove live model, MCP or authentication behavior.

## Slides

- [`docs/index.html`](docs/index.html): custom **scroll-snap HTML** workshop
  deck (not reveal.js). Open in a browser or serve the `docs/` folder.
- [`GitHub-Copilot-SDK.pptx`](GitHub-Copilot-SDK.pptx): the PowerPoint workshop deck.

```bash
python -m http.server -d docs 8000
# http://localhost:8000
```

## References

- [Python README at v1.0.13](https://github.com/github/copilot-sdk/blob/v1.0.13/python/README.md)
- [Tagged Python client](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/client.py),
  [session](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/session.py),
  [tools](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/tools.py)
- [Authentication](https://github.com/github/copilot-sdk/blob/v1.0.13/docs/auth/authenticate.md)
  and [BYOK](https://github.com/github/copilot-sdk/blob/v1.0.13/docs/auth/byok.md)
- [GitHub MCP server v1.12.0](https://github.com/github/github-mcp-server/tree/v1.12.0)
  and [MCP specification](https://modelcontextprotocol.io/)
- [All SDK releases](https://github.com/github/copilot-sdk/releases)

## License

[MIT](LICENSE)
