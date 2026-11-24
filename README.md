# Microsoft Copilot SDK: Python examples

Sixteen runnable Python examples for the **Microsoft Copilot SDK 2.0.1**
(formerly GitHub Copilot SDK), including the code on every code slide of the
talk. Each one ran live on November 24, 2026, on macOS and in GitHub Codespaces.

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/jeffrey-groneberg/ghcp_sdk?quickstart=1)

## Start in a Codespace

Open the badge above. The Codespace installs `microsoft-copilot-sdk==2.0.1`
with its runtime and signs you in with the Codespace's own GitHub token, so you
can start right away in its terminal:

```bash
python examples/01_simple_chat.py
```

You need a GitHub account with Copilot access. Which models you get, and who
pays, follow your Copilot plan and your organization's policies.

## Or run it locally

You need Python 3.11 or later. You don't need GitHub Copilot CLI or Node.js.

```bash
git clone https://github.com/jeffrey-groneberg/ghcp_sdk.git
cd ghcp_sdk
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
gh auth login                                        # or set COPILOT_GITHUB_TOKEN
python examples/01_simple_chat.py
```

The SDK downloads its matching runtime (1.0.114) on first use, or up front with
`python -m copilot download-runtime --in-process`. An existing `copilot login`
also works for sign-in.

## The examples

Run them from the repository root. [examples/README.md](examples/README.md)
has every command and the output to expect, and each example has a short
walkthrough next to it.

| # | Example | What it shows | Deck slide |
|---|---|---|---|
| 01 | [First app](examples/01_simple_chat.md) | One question, one answer, no tools | 17 |
| 02 | [Custom tool](examples/02_custom_tools.md) | A typed Python function as a tool | 19 |
| 03 | [Custom agents](examples/03_custom_agents.md) | A reviewer and a fixer, each with its own tools, in one session | 21 |
| 04 | [Hooks](examples/04_hooks.md) | Your code before and after every tool call | |
| 05 | [MCP servers](examples/05_mcp_servers.md) | GitHub's remote MCP server with an exact tool allow-list | 20 |
| 06 | [Durable sessions](examples/06_session_resume.md) | A new process resumes a session by its ID | 25 |
| 07 | [Human in the loop](examples/07_human_in_the_loop.md) | The agent asks you a question; you approve one exact command | |
| 08 | [Sandbox bypass](examples/08_sandbox.md) | A sandbox with one human-approved exception | |
| 09 | [Events](examples/09_events.md) | Every step of the loop as an event | 18 |
| 10 | [Identity](examples/10_identity.md) | Empty mode: each session runs as its user, with only your tools | 24 |
| 11 | [Connections](examples/11_connections.md) | In your process, as a child process, or a shared runtime server | 29 |
| 12 | [Approval in code](examples/12_approval.md) | A hook block list, then exact-match approval | 32 |
| 13 | [Containment](examples/13_containment.md) | Every request approved, and the sandbox still blocks | 33 |
| 14 | [Your storage](examples/14_session_fs.md) | The session journal in your own storage, resumed by ID | 25 |
| 15 | [Cost](examples/15_cost.md) | An AI-credit cap, per-call usage and session totals | 30 |
| 16 | [Skills](examples/16_skills.md) | A `SKILL.md` the agent loads when it needs it | |

[azure_foundry_byok.py](examples/azure_foundry_byok.py) uses your own Microsoft
Foundry model instead of Copilot's models; it needs your endpoint, key and
deployment name.

## What changed from SDK 1.0.13

Code written for 1.x stops before its first model call on 2.0, because the
client needs an explicit mode. The full list is in the
[v2 breaking changes](https://github.com/microsoft/copilot-sdk/blob/v2.0.1/docs/v2-breaking-changes.md).

| | 1.0.13 | 2.0.1 |
|---|---|---|
| Package | `github-copilot-sdk` (deprecated) | `microsoft-copilot-sdk`; `import copilot` is unchanged |
| Client | `CopilotClient()` | `CopilotClient(mode="coding-agent")` for one user, `mode="empty"` for many |
| Session options | Flat: `available_tools=`, `on_permission_request=`, `streaming=` | Grouped: `tools={"available_tools": ...}`, `permissions={"on_request": ...}`, `events={"streaming": ...}`; the old names raise `TypeError` |
| Runtime | A child process by default; `connection=` | In your process by default; `runtime=` with `for_spawned_stdio()`, `for_spawned_tcp()` or `for_tcp(host, port)` |
| Your own models | `provider=ProviderConfig(...)` | `inference={"providers": [...]}` |

## Experimental APIs in these examples

The SDK 2.0.1 source marks these as experimental, so they may change or be
removed in a later release:

- **Types** ("Experimental: this type is part of an experimental API and may
  change or be removed."): `SandboxConfig`, `SandboxConfigUserPolicy`,
  `SandboxConfigUserPolicyFilesystem` and `SandboxConfigUserPolicyNetwork`
  (08, 13); `PermissionDecisionApproveOnce` and `PermissionDecisionReject`
  (07, 08, 12); `AgentSelectRequest` (03); `SessionAuthStatus` (10);
  `SessionFSReaddirWithTypesEntry` (14).
- **API groups** ("Experimental: this API group is experimental and may change
  or be removed."): `AgentApi` (`session.rpc.agent`, 03), `GitHubAuthApi`
  (`session.rpc.git_hub_auth`, 10) and `UsageApi` (`session.rpc.usage`, 15).
- **Session limits**: `SessionLimitsConfig` ("Experimental limits for the
  session's current accounting window"), that is `execution.limits.max_ai_credits` (15).

## Keep it safe

- `PermissionHandler.approve_all` approves every request. The examples use it
  only with read-only tools, in disposable demo folders, or, in example 13, to
  show that the sandbox still holds.
- By default the runtime runs in your process. That isn't a sandbox and gives
  no crash isolation.
- Exposure, approval and containment are separate layers. A tool allow-list
  doesn't approve calls, and an approved call can still reach too far; examples
  10, 12 and 13 show one layer each.
- The sandbox runs shell commands; built-in file tools are policy-checked. It
  doesn't cover remote MCP servers, your own tool handlers or the in-process
  runtime itself.

## Notes for Codespaces

- **Sign-in** uses the Codespace's `GITHUB_TOKEN`, which the terminal has. In
  `gh codespace ssh`, start a login shell (`bash -l`) to get it.
- **Sandbox**: the dev container turns off Docker's default seccomp and
  AppArmor profiles and its masked `/proc` paths (`securityOpt` in
  [.devcontainer/devcontainer.json](.devcontainer/devcontainer.json)), so
  Bubblewrap, the sandbox's Linux backend, can create its namespaces. Without
  that, every sandboxed command fails with a `bwrap:` error. The container gets
  no extra capabilities.
- **SAML single sign-on**: if your account belongs to an organization that
  enforces SAML SSO, such as microsoft, the Codespace's token isn't authorized
  for it, and example 05 can't read `microsoft/copilot-sdk`. Run
  `gh issue list -R microsoft/copilot-sdk` and open the authorization link it
  prints, or pass another repository:
  `python examples/05_mcp_servers.py github/github-mcp-server`.

## Offline tests

```bash
python -m unittest discover -s examples/tests -v
```

They need no sign-in, runtime or model. They run every example against a fake
client and check each option against the SDK 2.0.1 signatures, and they test
the approval logic of examples 07, 08 and 12 and the session store of 14.

## The October 2026 deck (archived)

[docs/index.html](docs/index.html), published at
<https://jeffrey-groneberg.github.io/ghcp_sdk/>, and `GitHub-Copilot-SDK.pptx`
are the October 2026 deck for GitHub Copilot SDK 1.0.13. They're kept as they
were; their code doesn't run on SDK 2.0.

## References

- [v2 breaking changes](https://github.com/microsoft/copilot-sdk/blob/v2.0.1/docs/v2-breaking-changes.md)
  and the [Python README](https://github.com/microsoft/copilot-sdk/blob/v2.0.1/python/README.md), tag v2.0.1
- [Getting started](https://github.com/microsoft/copilot-sdk/blob/v2.0.1/docs/getting-started.md)
  and [multi-tenancy](https://github.com/microsoft/copilot-sdk/blob/v2.0.1/docs/setup/multi-tenancy.md)
- [microsoft-copilot-sdk 2.0.1 on PyPI](https://pypi.org/project/microsoft-copilot-sdk/2.0.1/)
  and [all releases](https://github.com/microsoft/copilot-sdk/releases)

## License

[MIT](LICENSE)
