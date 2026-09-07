# Examples — student guide

**Workshop baseline:** `github-copilot-sdk==1.0.13`, Python 3.11+, Pydantic 2+,
Copilot CLI/runtime 1.0.83. See [setup and release notes](../README.md).

Each numbered `.py` is independently runnable; its `.md` explains the code,
shows a flow diagram, and offers exercises. Run scripts from the repository
root. No shared application framework is required.

```mermaid
flowchart LR
    A[01 Streaming] --> B[02 Custom tools]
    B --> C[03 Agents]
    C --> D[04 Hooks]
    D --> E[05 Remote MCP]
    E --> F[06 Persistence]
    F --> G[07 Human input]
```

| Guide | Concepts | Version-pinned authority |
|---|---|---|
| [01 Streaming](01_simple_chat.md) | Client identity, events, bounded completion | [Session implementation](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/session.py) |
| [02 Tools](02_custom_tools.md) | Pydantic schemas and fictional weather | [Tool implementation](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/tools.py) |
| [03 Agents](03_custom_agents.md) | Select and verify researcher → reviewer | [Custom agents](https://github.com/github/copilot-sdk/blob/v1.0.13/docs/features/custom-agents.md) |
| [04 Hooks](04_hooks.md) | Pre/post callbacks and policy distinctions | [Hook types/dispatch](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/session.py) |
| [05 MCP](05_mcp_servers.md) | Remote HTTP, credentials, issue tool allowlists | [MCP](https://github.com/github/copilot-sdk/blob/v1.0.13/docs/features/mcp.md) |
| [06 Persistence](06_session_resume.md) | Detach, saved IDs, cold resume | [Client implementation](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/client.py) |
| [07 Human input](07_human_in_the_loop.md) | Permission variants, legacy choices, deadlines | [Input/permission types](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/session.py) |

## Shared conventions

- Model: `gpt-5-mini`; inspect `await client.list_models()` before switching.
  Model calls may consume your account's quota; no cost guarantee is implied.
- Context managers clean up the session and owned client. In 1.0.13,
  session `disconnect()` uses **detach**, retaining persisted state.
- `send_and_wait(..., timeout=...)` still emits events to `session.on`.
  Timeout **raises `TimeoutError`**; `None` means idle without an assistant
  message. Examples deliberately raise if a required reply is absent.
- All conversations have deadlines; callbacks do not swallow cancellation.
  Timeout stops waiting, not necessarily remote agent work.
- Tools are explicitly scoped. `available_tools` filters the entire merged
  catalogue: `builtin:view`, `custom:get_weather`, `mcp:github-list_issues`.
  Source: [tagged ToolSet implementation/tests](https://github.com/github/copilot-sdk/blob/v1.0.13/python/test_tool_set.py).
- `approve_all` is a trusted-workshop convenience, **not a sandbox**. Use a
  non-sensitive checkout and least-privilege credentials. Example 07 asks
  before shell execution and denies unexpected permission kinds.
- Console traces log tool names, not credentials or full MCP payloads.

## Run and inspect

```bash
python examples/01_simple_chat.py
python -m unittest discover -s examples/tests -v  # mocked, no model calls
python -c "import copilot, pathlib; print(pathlib.Path(copilot.__file__).parent)"
```

The source walkthroughs are pinned to the stable release. Consult generated
Python types when narrative docs and actual signatures differ; do not copy
unreleased examples without checking the installed version.
