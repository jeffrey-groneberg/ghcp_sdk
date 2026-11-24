# 06 · Durable sessions

Deck slide 25 · [Source](06_session_resume.py) · [Session persistence](https://github.com/microsoft/copilot-sdk/blob/v2.0.1/docs/features/session-persistence.md)

Run it twice, as two processes. The second process resumes the session by its
ID and still knows the code word.

## Run it

```bash
python examples/06_session_resume.py create team-assistant-01
python examples/06_session_resume.py resume team-assistant-01
```

## How it works

```python
async with CopilotClient(mode="coding-agent") as client:  # a new process
    if step == "create":
        session = await client.create_session(
            session_id=session_id, tools={"available_tools": []})
    else:                                     # same ID, after a restart
        session = await client.resume_session(
            session_id, tools={"available_tools": []})
    reply = await session.send_and_wait(PROMPTS[step], timeout=60)
```

- You choose the ID; let it say whose session it is and what for, such as
  `user-alice-pr-review-42`. Without one, the runtime generates an ID that you
  must store.
- The runtime appends everything about a session to its journal: messages,
  tool calls and their results, plans and checkpoints. By default it lives in
  `~/.copilot/session-state/<id>/`; example 14 keeps it in your own storage.
- Leaving the client detaches the session and keeps its journal;
  `client.delete_session(id)` deletes it.
- Resuming doesn't restore callbacks, tool handlers or provider keys. Pass them
  again, as this example does with `tools`.

## Output from a live run

```text
create team-assistant-01: OK
resume team-assistant-01: AMBER-4711
```

## Try this next

- Resume with another model: `resume_session(session_id, model="...", ...)`.
- `await client.list_sessions()` lists the sessions the runtime knows.
