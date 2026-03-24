# GitHub Copilot SDK — Python Examples

Six self-contained examples demonstrating the core capabilities of the
[GitHub Copilot SDK](https://github.com/github/copilot-sdk) for Python.

## Prerequisites

- **Python 3.10+**
- **[Copilot CLI](https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli)** installed and signed in, **or** `COPILOT_GITHUB_TOKEN` set in your environment
- **Node.js / npx** (only for Example 5 — MCP server)

## Quick Start

```bash
# Clone the repository
git clone https://github.com/your-org/ghcp-sdk-examples.git
cd ghcp-sdk-examples

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows

# Install dependencies
pip install -r requirements.txt
```

## Examples

| # | File | Capability | Description |
|---|------|-----------|-------------|
| 1 | [`01_simple_chat.py`](examples/01_simple_chat.py) | **Streaming Chat** | Create a session, stream tokens, multi-turn conversation |
| 2 | [`02_custom_tools.py`](examples/02_custom_tools.py) | **Custom Tools** | `@define_tool` with Pydantic models — weather API + unit converter |
| 3 | [`03_custom_agents.py`](examples/03_custom_agents.py) | **Custom Agents** | Three agents (researcher, writer, reviewer) with auto-delegation |
| 4 | [`04_hooks.py`](examples/04_hooks.py) | **Hooks** | All 6 hook types — access control, secret redaction, prompt shortcuts |
| 5 | [`05_mcp_and_persistence.py`](examples/05_mcp_and_persistence.py) | **MCP + Persistence** | Filesystem MCP server + resumable sessions across restarts |
| 6 | [`06_human_in_the_loop.py`](examples/06_human_in_the_loop.py) | **Human-in-the-Loop** | Interactive permission approvals + user input requests |

## Running the Examples

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

# 6. Human-in-the-loop (interactive approvals + user input)
python examples/06_human_in_the_loop.py
```

## Project Structure

```
ghcp-sdk-examples/
├── README.md
├── pyproject.toml
├── requirements.txt
├── LICENSE
├── .gitignore
└── examples/
    ├── README.md
    ├── 01_simple_chat.py
    ├── 02_custom_tools.py
    ├── 03_custom_agents.py
    ├── 04_hooks.py
    ├── 05_mcp_and_persistence.py
    └── 06_human_in_the_loop.py
```

## License

[MIT](LICENSE)
