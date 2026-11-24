# 03 · Custom agents

Deck slide 21 · [Source](03_custom_agents.py) · [Custom agents](https://github.com/microsoft/copilot-sdk/blob/v2.0.1/docs/features/custom-agents.md)

One session, two roles: a reviewer that only reads and a fixer that may edit.
They work on a disposable demo repository whose `calc.py` has a planted bug:
`add(a, b)` returns `a - b`.

## Run it

```bash
python examples/03_custom_agents.py
```

## How it works

```python
reviewer = {"name": "reviewer", "description": "Finds bugs, never edits",
            "prompt": "Review only.", "tools": ["view", "grep", "glob"]}
fixer = {"name": "fixer", "description": "Fixes one bug, minimal edit",
         "prompt": "Make the smallest fix.", "tools": ["view", "edit"]}
session = await client.create_session(
    working_directory=str(repo),
    permissions={"on_request": PermissionHandler.approve_all},  # demo repo
    agents={"definitions": [reviewer, fixer], "selected": "reviewer"})
...
await session.rpc.agent.select(AgentSelectRequest(name="fixer"))
```

- Each agent is a dictionary with a name, a description, a prompt and its own
  tools. `agents.selected` picks the first one.
- `session.rpc.agent.select` switches the agent mid-conversation, and the
  history stays. The `AgentApi` group (`session.rpc.agent`) and
  `AgentSelectRequest` are experimental in SDK 2.0.1.
- `_demo_repo.py` creates the repository in a temporary folder, so the fixer
  edits a disposable copy. `approve_all` approves every request, including edits
  outside that folder, so keep it to demos. The example prints `git diff` at
  the end.

## Output from a live run

```text
reviewer: **Bug:** In `calc.py`, `add(a, b)` returns `a - b` instead of `a + b`. ...
fixer: I fixed `add` in `calc.py` so it now returns `a + b`, and I removed the old bug comment. ...
@@ -2 +2 @@ def add(a, b):
-    return a - b   # bug: should be a + b
+    return a + b
```

## Try this next

- Ask the reviewer to fix the bug. It has no edit tool, so it can only
  describe the fix.
