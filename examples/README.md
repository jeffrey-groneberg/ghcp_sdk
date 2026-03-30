# GitHub Copilot SDK — Python Examples

Five self-contained examples that demonstrate the core capabilities of the
[GitHub Copilot SDK](https://github.com/github/copilot-sdk).

## Prerequisites

```bash
pip install github-copilot-sdk pydantic
```

You also need the [Copilot CLI](https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli)
installed and signed in, **or** set `COPILOT_GITHUB_TOKEN` in your environment.

## Examples

| # | File | Capability | What it shows |
|---|------|-----------|---------------|
| 1 | `01_simple_chat.py` | **Streaming Chat** | Create a session, stream tokens, multi-turn conversation |
| 2 | `02_custom_tools.py` | **Custom Tools** | `@define_tool` with Pydantic models — weather API + unit converter |
| 3 | `03_custom_agents.py` | **Custom Agents** | Three agents (researcher, writer, reviewer) with explicit handoff via `session.rpc.agent.select()` |
| 4 | `04_hooks.py` | **Hooks** | All 6 hook types — access control, secret redaction, prompt shortcuts |
| 5 | `05_mcp_and_persistence.py` | **MCP + Persistence** | Filesystem MCP server + resumable sessions across restarts |
| 6 | `06_human_in_the_loop.py` | **Human-in-the-Loop** | Interactive permission approvals + agent asks user questions |

## Running

```bash
# 1. Simple chat with streaming
python examples/01_simple_chat.py

# 2. Custom tools (weather + unit converter)
python examples/02_custom_tools.py

# 3. Custom agents (researcher / writer / reviewer)
python examples/03_custom_agents.py

# 4. Hooks (access control, redaction, shortcuts)
python examples/04_hooks.py

# 5. MCP server + session persistence
python examples/05_mcp_and_persistence.py              # first run
python examples/05_mcp_and_persistence.py --resume      # resume later

# 6. Human-in-the-loop (interactive approvals + user questions)
python examples/06_human_in_the_loop.py
```
