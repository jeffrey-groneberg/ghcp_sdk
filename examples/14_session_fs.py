"""
Example 14: the session journal in your own storage, resumed by ID.

With session_fs, the runtime reads and writes a session's journal and state
files through your provider instead of its own disk. This provider keeps each
session in its own folder under STORE; swap its pathlib calls for your blob
storage or database client to keep journals there. Run it twice: the second
process resumes the session from your store alone. Empty mode accepts
session_fs as its storage. SessionFSReaddirWithTypesEntry is experimental in
SDK 2.0.1.

Run:
    python examples/14_session_fs.py create
    python examples/14_session_fs.py resume
"""

import asyncio
import datetime as dt
import os
import shutil
import sys
import tempfile
from pathlib import Path

from copilot import CopilotClient, SessionFsFileInfo, SessionFsProvider
from copilot.rpc import SessionFSReaddirWithTypesEntry, SessionFSReaddirWithTypesEntryType

STORE = Path(tempfile.gettempdir()) / "copilot-session-store"  # your storage
SESSION_ID = "team-assistant-journal-01"
PROMPTS = {
    "create": "Remember this code word: AMBER-4711. Reply with OK only.",
    "resume": "What was the code word I gave you earlier? Reply with the word only.",
}


class FolderFs(SessionFsProvider):
    """Maps the runtime's paths for one session into STORE/<session id>."""

    def __init__(self, session_id: str):
        self.root = (STORE / session_id).resolve()

    def _path(self, path: str) -> Path:
        full = (self.root / path.lstrip("/")).resolve()
        if not full.is_relative_to(self.root):
            raise PermissionError(f"outside the session's folder: {path}")
        return full

    async def read_file(self, path):
        return self._path(path).read_text(encoding="utf-8")

    async def write_file(self, path, content, mode=None):
        target = self._path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    async def append_file(self, path, content, mode=None):
        target = self._path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as file:
            file.write(content)

    async def exists(self, path):
        return self._path(path).exists()

    async def stat(self, path):
        target = self._path(path)
        info = target.stat()
        mtime = dt.datetime.fromtimestamp(info.st_mtime, tz=dt.UTC)
        return SessionFsFileInfo(is_file=target.is_file(), is_directory=target.is_dir(),
                                 size=info.st_size, mtime=mtime, birthtime=mtime)

    async def mkdir(self, path, recursive, mode=None):
        self._path(path).mkdir(parents=recursive, exist_ok=recursive)

    async def readdir(self, path):
        return sorted(entry.name for entry in self._path(path).iterdir())

    async def readdir_with_types(self, path):
        kind = SessionFSReaddirWithTypesEntryType
        return [SessionFSReaddirWithTypesEntry(
                    name=entry.name, type=kind.DIRECTORY if entry.is_dir() else kind.FILE)
                for entry in sorted(self._path(path).iterdir())]

    async def rm(self, path, recursive, force):
        target = self._path(path)
        if target.is_dir():
            shutil.rmtree(target) if recursive else target.rmdir()
        elif target.exists() or not force:
            target.unlink()

    async def rename(self, src, dest):
        target = self._path(dest)
        target.parent.mkdir(parents=True, exist_ok=True)
        self._path(src).replace(target)


async def main(step: str) -> None:
    if step == "create":  # start from an empty store
        shutil.rmtree(STORE / SESSION_ID, ignore_errors=True)
    async with CopilotClient(
        mode="empty",
        session_fs={"initial_working_directory": "/workspace",
                    "session_state_path": "/session-state", "conventions": "posix"},
    ) as client:
        options = {"state": {"create_session_fs_provider": lambda s: FolderFs(s.session_id)},
                   "tools": {"available_tools": []}}
        if step == "create":
            session = await client.create_session(session_id=SESSION_ID, **options)
        else:
            session = await client.resume_session(SESSION_ID, **options)
        # Detach before the client stops: the final journal writes still go through FolderFs.
        async with session:
            reply = await session.send_and_wait(PROMPTS[step], timeout=60)
            print(f"{step} {SESSION_ID}: {reply.data.content if reply else 'no answer'}")
    for file in sorted((STORE / SESSION_ID).rglob("*")):
        if file.is_file():
            print(f"  {file.relative_to(STORE)} ({file.stat().st_size} bytes)")
    runtime_home = Path(os.environ.get("COPILOT_HOME", "~/.copilot")).expanduser()
    print("in the runtime's own session-state:",
          (runtime_home / "session-state" / SESSION_ID).exists())


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in PROMPTS:
        sys.exit("usage: python examples/14_session_fs.py create|resume")
    asyncio.run(main(sys.argv[1]))
