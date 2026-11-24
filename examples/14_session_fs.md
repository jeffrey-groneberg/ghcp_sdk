# 14 · Your storage

Deck slide 25 (sessionFs) · [Source](14_session_fs.py) · [Session persistence](https://github.com/microsoft/copilot-sdk/blob/v2.0.1/docs/features/session-persistence.md) · [sessionFs](https://github.com/microsoft/copilot-sdk/blob/v2.0.1/docs/setup/multi-tenancy.md#sessionfs)

With `session_fs`, the runtime keeps a session's journal and state files in
storage you provide. Run it twice: the second process resumes the session from
your store alone.

## Run it

```bash
python examples/14_session_fs.py create
python examples/14_session_fs.py resume
```

## How it works

```python
async with CopilotClient(
    mode="empty",
    session_fs={"initial_working_directory": "/workspace",
                "session_state_path": "/session-state", "conventions": "posix"},
) as client:
    options = {"state": {"create_session_fs_provider": lambda s: FolderFs(s.session_id)},
               "tools": {"available_tools": []}}
```

- `session_fs` tells the runtime which paths it sees. For each session,
  `state.create_session_fs_provider` returns a provider, and the runtime reads
  and writes `/session-state/events.jsonl` and the other state files through it.
- `FolderFs` implements the ten methods of `SessionFsProvider` with `pathlib`:
  one folder per session under `STORE`, and no paths outside it. Swap those
  calls for your blob storage or database client.
- Empty mode accepts `session_fs` as its storage, so the client needs no
  `base_directory`.
- The session is detached (`async with session`) before the client stops,
  because the last journal writes still go through your provider.
- Shell tools don't run through `session_fs`. Keep tenants in separate
  namespaces, and reconnect a resumed session to its own.
- `SessionFSReaddirWithTypesEntry` is experimental in SDK 2.0.1.

## Output from a live run

```text
create team-assistant-journal-01: OK
  team-assistant-journal-01/session-state/checkpoints/index.md (172 bytes)
  team-assistant-journal-01/session-state/events.jsonl (25805 bytes)
  team-assistant-journal-01/session-state/workspace.yaml (273 bytes)
in the runtime's own session-state: False

resume team-assistant-journal-01: AMBER-4711
  team-assistant-journal-01/session-state/checkpoints/index.md (172 bytes)
  team-assistant-journal-01/session-state/events.jsonl (39076 bytes)
  team-assistant-journal-01/session-state/workspace.yaml (273 bytes)
in the runtime's own session-state: False
```
