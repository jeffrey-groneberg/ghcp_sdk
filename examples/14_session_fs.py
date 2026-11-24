"""
Example 14: the session journal in your own storage, resumed by ID.

With session_fs, the runtime reads and writes a session's journal and state
files through your provider instead of its own disk. This provider keeps each
file as a row in a SQLite database you own; object storage or tenant-scoped
paths work the same way. Run it twice: the second process resumes the session
from the database alone. Empty mode accepts session_fs as its storage.

Run:
    python examples/14_session_fs.py create
    python examples/14_session_fs.py resume
"""

import asyncio
import datetime as dt
import errno
import sqlite3
import sys
import tempfile
from pathlib import Path

from copilot import CopilotClient, SessionFsFileInfo, SessionFsProvider
from copilot.rpc import SessionFSReaddirWithTypesEntry, SessionFSReaddirWithTypesEntryType

DB = Path(tempfile.gettempdir()) / "copilot-session-store.sqlite"
SESSION_ID = "team-assistant-journal-01"
PROMPTS = {
    "create": "Remember this code word: AMBER-4711. Reply with OK only.",
    "resume": "What was the code word I gave you earlier? Reply with the word only.",
}


class SqliteFs(SessionFsProvider):
    """One session's files as rows: (session, path, content); content NULL is a folder."""

    def __init__(self, session_id: str):
        self.sid, self.db = session_id, sqlite3.connect(DB)
        self.db.execute("CREATE TABLE IF NOT EXISTS files"
                        " (session TEXT, path TEXT, content TEXT, PRIMARY KEY (session, path))")

    def _rows(self) -> dict[str, str | None]:
        rows = self.db.execute("SELECT path, content FROM files WHERE session = ?", (self.sid,))
        return {"/": None} | dict(rows.fetchall())

    def _put(self, path: str, content: str | None) -> None:
        parents = ["/".join(path.split("/")[:i]) for i in range(2, path.count("/") + 1)]
        with self.db:
            self.db.executemany("INSERT OR IGNORE INTO files VALUES (?, ?, NULL)",
                                [(self.sid, p) for p in parents])
            self.db.execute("INSERT OR REPLACE INTO files VALUES (?, ?, ?)",
                            (self.sid, path, content))

    def _children(self, path: str) -> dict[str, bool]:  # name -> is folder
        prefix, rows = path.rstrip("/") + "/", self._rows()
        if path not in rows:
            raise FileNotFoundError(errno.ENOENT, "no such folder", path)
        names = {p[len(prefix):].split("/")[0] for p in rows if p.startswith(prefix) and p != "/"}
        return {n: rows.get(prefix + n, None) is None for n in sorted(names)}

    async def read_file(self, path):
        content = self._rows().get(path)
        if content is None:
            raise FileNotFoundError(errno.ENOENT, "no such file", path)
        return content

    async def write_file(self, path, content, mode=None):
        self._put(path, content)

    async def append_file(self, path, content, mode=None):
        self._put(path, (self._rows().get(path) or "") + content)

    async def exists(self, path):
        return path in self._rows()

    async def stat(self, path):
        rows, now = self._rows(), dt.datetime.now(dt.UTC)
        if path not in rows:
            raise FileNotFoundError(errno.ENOENT, "no such file", path)
        content = rows[path]
        return SessionFsFileInfo(is_file=content is not None, is_directory=content is None,
                                 size=len(content or ""), mtime=now, birthtime=now)

    async def mkdir(self, path, recursive, mode=None):
        if path not in self._rows():
            self._put(path, None)

    async def readdir(self, path):
        return list(self._children(path))

    async def readdir_with_types(self, path):
        kind = SessionFSReaddirWithTypesEntryType
        return [SessionFSReaddirWithTypesEntry(name=n, type=kind.DIRECTORY if folder else kind.FILE)
                for n, folder in self._children(path).items()]

    async def rm(self, path, recursive, force):
        if path not in self._rows() and not force:
            raise FileNotFoundError(errno.ENOENT, "no such file", path)
        with self.db:
            self.db.execute("DELETE FROM files WHERE session = ? AND (path = ? OR path LIKE ?)",
                            (self.sid, path, path.rstrip("/") + "/%"))

    async def rename(self, src, dest):
        with self.db:
            self.db.execute("DELETE FROM files WHERE session = ? AND path = ?", (self.sid, dest))
            self.db.execute("UPDATE files SET path = ? || substr(path, ?) WHERE session = ?"
                            " AND (path = ? OR path LIKE ?)",
                            (dest, len(src) + 1, self.sid, src, src.rstrip("/") + "/%"))


async def main(step: str) -> None:
    if step == "create":  # start from an empty journal
        with SqliteFs(SESSION_ID).db as db:
            db.execute("DELETE FROM files WHERE session = ?", (SESSION_ID,))
    async with CopilotClient(
        mode="empty",
        session_fs={"initial_working_directory": "/workspace",
                    "session_state_path": "/session-state", "conventions": "posix"},
    ) as client:
        options = {"state": {"create_session_fs_provider": lambda s: SqliteFs(s.session_id)},
                   "tools": {"available_tools": []}}
        if step == "create":
            session = await client.create_session(session_id=SESSION_ID, **options)
        else:
            session = await client.resume_session(SESSION_ID, **options)
        reply = await session.send_and_wait(PROMPTS[step], timeout=60)
        print(f"{step} {SESSION_ID}: {reply.data.content if reply else 'no answer'}")
    print(f"journal rows in {DB}:")
    for path, content in sorted(SqliteFs(SESSION_ID)._rows().items()):
        if content is not None:
            print(f"  {path} ({len(content)} characters)")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in PROMPTS:
        sys.exit("usage: python examples/14_session_fs.py create|resume")
    asyncio.run(main(sys.argv[1]))
