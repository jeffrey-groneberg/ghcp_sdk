# 01 · First app

Deck slide 17 · [Source](01_simple_chat.py) · [Getting started](https://github.com/microsoft/copilot-sdk/blob/v2.0.1/docs/getting-started.md)

The whole program behind "Install. Sign in. First answer.": one question, one
answer, no tools.

## Run it

```bash
python examples/01_simple_chat.py
```

## How it works

```python
async with CopilotClient(mode="coding-agent") as client:
    async with await client.create_session(
        tools={"available_tools": []},  # text only: no tools this time
    ) as session:
        reply = await session.send_and_wait(
            "In one sentence: what is an agent harness?", timeout=60)
```

- SDK 2.0 requires `mode`. `coding-agent` gives one user CLI-like tools and
  defaults; `empty` is for services with many users (example 10).
- Session options come in groups. `tools={"available_tools": []}` exposes no
  tools, so the model can only answer in text.
- `send_and_wait` sends the prompt and waits for the final answer. It raises
  `TimeoutError` after 60 seconds and returns `None` if the session goes idle
  without an answer.
- Leaving the `async with` blocks detaches the session and stops the runtime,
  which runs inside your process by default.

## Output from a live run

```text
An agent harness is the software scaffolding around an AI model that runs its loop: it supplies context and tools, executes the model's tool calls, feeds results back, and manages permissions, state, and termination so the model can act as an autonomous agent.
```

## Try this next

- List your models with `print([m.id for m in await client.list_models()])`,
  then pass one as `model="..."` to `create_session`.
- Ask a follow-up in the same session; it remembers the first question.
