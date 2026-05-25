# Examples — student guide

Each example in this folder ships with **two files**:

| File | What it is |
|------|------------|
| `0N_*.py` | Runnable, heavily-commented Python source |
| `0N_*.md` | A walkthrough with a mermaid flow diagram, line-by-line explanation, expected output, exercises and common pitfalls |

Read the `.md` first, then open the `.py` and tinker.

## Recommended reading order

```mermaid
flowchart LR
    A[01 Simple chat] --> B[02 Custom tools]
    B --> C[03 Custom agents]
    C --> D[04 Hooks]
    D --> E[05 MCP + persistence]
    E --> F[06 Human in the loop]
```

| # | Topic | Concepts |
|---|-------|----------|
| [01](01_simple_chat.md) | **Streaming chat** | Client / session lifecycle, event stream, `match`/`case` on SDK events |
| [02](02_custom_tools.md) | **Custom tools** | `@define_tool`, Pydantic schemas, request/response with `send_and_wait` |
| [03](03_custom_agents.md) | **Custom agents** | Multiple personas in one session, mid-conversation handoff |
| [04](04_hooks.md) | **Hooks** | Pre/post tool callbacks for audit, telemetry, soft policy |
| [05](05_mcp_and_persistence.md) | **MCP + persistence** | Attaching MCP servers, resuming a conversation by `session_id` |
| [06](06_human_in_the_loop.md) | **Human in the loop** | Custom permission handler + `ask_user` callback |

## How to run

```bash
# from the repo root
python examples/01_simple_chat.py
```

All examples default to the free `gpt-4.1` model — no quota worries while learning.

## Where to look up SDK symbols

Every README links to the relevant chapter in the upstream docs:
[github/copilot-sdk → docs/](https://github.com/github/copilot-sdk/tree/main/docs).
The SDK source you have installed locally is also a great reference:

```bash
# Where the SDK lives in your venv
python -c "import copilot, pathlib; print(pathlib.Path(copilot.__file__).parent)"
```

## Adapting the examples

Each guide ends with a **"Try this next"** section — small, focused exercises
that nudge you to take ownership of the example. Pick one and modify the code:
break things on purpose, add a new tool, change the model, swap the agent
persona. That's how the patterns stick.
