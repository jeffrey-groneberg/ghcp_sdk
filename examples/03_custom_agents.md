# 03 · Researcher, then reviewer

**GitHub Copilot SDK - an introduction**

[Runnable source](03_custom_agents.py) · [Student guide](README.md)

**Sources, SDK v1.0.13:** [custom agents](https://github.com/github/copilot-sdk/blob/v1.0.13/docs/features/custom-agents.md),
[generated RPC types](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/generated/rpc.py).

## Goal and boundary

Two named personas review the same workshop file,
`examples/01_simple_chat.py`, in one session. The **researcher** reads the
source and maps resource lifetimes; the **reviewer** checks error handling
and cleanup, using the preserved conversation and further reads as needed.
No earlier checkpoint must have been run.

```mermaid
sequenceDiagram
    participant Host
    participant Runtime
    Host->>Runtime: Create researcher session in repository root
    Host->>Runtime: agent.list(); agent.get_current()
    Host->>Host: Assert researcher is selected
    Host->>Runtime: Read target; explain resource lifetimes
    Runtime-->>Host: Final researcher message
    Host->>Runtime: agent.select(reviewer); agent.get_current()
    Host->>Host: Assert reviewer is selected
    Host->>Runtime: Review the same target for errors and cleanup
    Runtime-->>Host: Final reviewer message
```

## Important code

Both entries in `AGENTS` have a name, display label, description, system
prompt, and `["grep", "glob", "view"]` tools. The session applies the same
read-tool filter and explicitly uses this checkout:

```python
working_directory=str(REPO_ROOT),
custom_agents=AGENTS,
agent="researcher",
available_tools=ToolSet().add_builtin(["grep", "glob", "view"]),
```

`REPO_ROOT = Path(__file__).resolve().parents[1]`; launching from a different
shell directory therefore does not redirect the review to an unrelated
project. This is a working-directory choice, **not a filesystem boundary**.

Registering personas is not proof of selection. Check the initial
`current.agent.name == "researcher"`, then use the typed switch and assert
the returned state:

```python
await session.rpc.agent.select(AgentSelectRequest(name="reviewer"))
current = await session.rpc.agent.get_current()
if current.agent is None or current.agent.name != "reviewer":
    raise RuntimeError("The reviewer persona was not selected.")
```

The sample makes these checks **before** the corresponding prompt, rather
than trusting a response that sounds like a reviewer. The agent listing may
contain runtime-provided personas too; do not assume exactly two entries.

Session filters narrow the catalogue; per-agent filters narrow it further.
They are **tool exposure controls, not an OS sandbox**. Even read tools can
expose sensitive data. `approve_all` is a convenience for this trusted,
non-sensitive workshop checkout, not a production authorization system.

Each turn requires a final message within 120 seconds; the entire operation
has a 360-second deadline. Failed selection, missing messages, runtime
errors, timeout, and cancellation remain visible. Normal contexts detach
the session and stop the owned client.

## Run and inspect

```bash
python examples/03_custom_agents.py
```

**Illustrative output, not an observed model run:**

```text
Registered agents: researcher, reviewer, ...
Active persona: researcher
Researcher: <source-cited map of client, session and subscription lifetimes>
--- swapped --- Active persona: reviewer
Reviewer: <source-cited findings, or an explicit statement that no bug was evidenced>
```

The RPC assertions establish selection, not the factual quality of the
review. The prompt asks the reviewer to separate concrete defects from
optional improvements. Offline tests inject absent/wrong agents and verify
that the next prompt is never sent.

**Exercise:** mock an incorrect reviewer selection. An error must occur even
if the assistant would otherwise have produced plausible review prose.
