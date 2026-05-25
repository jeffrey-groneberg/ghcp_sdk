# GitHub Copilot SDK — Python Examples

Six minimal, self-contained examples that show off the core capabilities of the
[GitHub Copilot SDK](https://github.com/github/copilot-sdk) for Python (`github-copilot-sdk` ≥ 0.3.0).

Every example is < 100 lines, follows the official upstream patterns, and is
heavily commented so you can read it like a tutorial.

---

## 🚀 Fastest path: Open in Codespaces

Click the badge below and you'll get a fully-configured, browser-based dev
environment in ~60 seconds — Python, Node, the Copilot CLI, and all
dependencies pre-installed.

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/jeffrey-groneberg/ghcp_sdk?quickstart=1)

Once the Codespace boots, in the integrated terminal run:

```bash
copilot auth login          # one-time GitHub Copilot sign-in
python examples/01_simple_chat.py
```

That's it — skip straight to the [Examples](#examples) table below.

---

## 🖥️ Running locally

### Prerequisites

- **Python 3.10+** (3.12 recommended; matches the Codespace)
- **Node.js / `npx`** (only needed for example 5 — MCP server)
- A **GitHub Copilot subscription** (any tier including the free one)
- The **[Copilot CLI](https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli)**
  installed and signed in via `copilot auth login`, *or* `COPILOT_GITHUB_TOKEN`
  set in your environment

### Setup

```bash
git clone https://github.com/jeffrey-groneberg/ghcp_sdk.git
cd ghcp_sdk

python -m venv .venv
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\Activate.ps1       # Windows PowerShell

pip install -r requirements.txt
```

> **Windows tip:** export `PYTHONIOENCODING=utf-8` before running the examples
> so the agent's UTF-8 output renders correctly on the legacy `cp1252` console.

---

## Examples

All examples default to `gpt-4.1` (free, multiplier × 0). Swap to any model
returned by `await client.list_models()` if you want to experiment.

Each example has a **dedicated walkthrough** with mermaid diagrams, line-by-line
explanations and student exercises — open the linked `.md` files for the full
story, then read the `.py` to see it in action.

| # | Walkthrough | Source | Capability |
|---|------|--------|------------|
| 1 | [`01_simple_chat.md`](examples/01_simple_chat.md) | [`.py`](examples/01_simple_chat.py) | **Streaming chat** — client/session lifecycle, event-driven token streaming |
| 2 | [`02_custom_tools.md`](examples/02_custom_tools.md) | [`.py`](examples/02_custom_tools.py) | **Custom tools** — `@define_tool` with Pydantic parameter schemas |
| 3 | [`03_custom_agents.md`](examples/03_custom_agents.md) | [`.py`](examples/03_custom_agents.py) | **Custom agents** — multiple personas + mid-conversation handoff |
| 4 | [`04_hooks.md`](examples/04_hooks.md) | [`.py`](examples/04_hooks.py) | **Hooks** — `on_pre_tool_use` / `on_post_tool_use` for audit / policy |
| 5 | [`05_mcp_and_persistence.md`](examples/05_mcp_and_persistence.md) | [`.py`](examples/05_mcp_and_persistence.py) | **MCP + resumable sessions** — filesystem MCP server + `resume_session` |
| 6 | [`06_human_in_the_loop.md`](examples/06_human_in_the_loop.md) | [`.py`](examples/06_human_in_the_loop.py) | **Human-in-the-loop** — custom permission + `ask_user` callbacks |

See [`examples/README.md`](examples/README.md) for the recommended reading order.

### Run them

```bash
python examples/01_simple_chat.py
python examples/02_custom_tools.py
python examples/03_custom_agents.py
python examples/04_hooks.py
python examples/05_mcp_and_persistence.py            # first run
python examples/05_mcp_and_persistence.py --resume   # continue the same conversation
python examples/06_human_in_the_loop.py              # interactive — type answers when prompted
```

---

## 📚 Slides

A reveal.js deck that walks through every example lives in
[`docs/index.html`](docs/index.html). Open it directly in a browser, or serve
the `docs/` folder with any static server:

```bash
python -m http.server -d docs 8000
# then visit http://localhost:8000
```

---

## Project layout

```
ghcp_sdk/
├── .devcontainer/          # Codespaces config (Python 3.12 + Node + gh CLI)
├── docs/
│   └── index.html          # reveal.js teaching deck
├── examples/
│   ├── 01_simple_chat.py
│   ├── 02_custom_tools.py
│   ├── 03_custom_agents.py
│   ├── 04_hooks.py
│   ├── 05_mcp_and_persistence.py
│   └── 06_human_in_the_loop.py
├── pyproject.toml
├── requirements.txt
└── README.md
```

---

## License

[MIT](LICENSE)
