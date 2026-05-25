"""
Example 05 — MCP servers + session persistence

Two features rolled into one short file because they're often used
together when building real assistants:

  1. **MCP servers** — the [Model Context Protocol](https://modelcontextprotocol.io)
     is the standard plugin format for LLM tools. Hundreds of community
     servers already exist (filesystem, git, GitHub, Notion, ...). The SDK
     attaches them with a single `mcp_servers={...}` kwarg.

  2. **Session persistence** — every session has an ID. Pass the *same* ID
     to `create_session()` once and to `resume_session()` later and the
     Copilot CLI replays the full conversation history into the model.
     This is how you build chatbots that "remember" across restarts.

Run:
    python examples/05_mcp_and_persistence.py            # first turn
    python examples/05_mcp_and_persistence.py --resume   # continue later
"""

import asyncio
import os
import sys
import tempfile

from copilot import CopilotClient
from copilot.session import PermissionHandler


# A stable, app-specific session ID. Production code would pick a UUID
# per user / per conversation and store it in your DB; this constant makes
# the demo easy to re-run.
SESSION_ID = "demo-mcp-persistent-session"

# Where the demo files live. We use a temp dir so the example is hermetic
# and the filesystem MCP server can't accidentally see the rest of your disk.
WORKDIR = os.path.join(tempfile.gettempdir(), "copilot-demo")


# MCP server configuration.
#
#   type     → 'local' = spawn a process and talk JSON-RPC over stdio
#              ('http' / 'sse' / 'streamable-http' are also supported)
#   command  → executable to launch (here `npx` to download on the fly)
#   args     → CLI args; the trailing positional `WORKDIR` is what limits
#              the server to that directory — without it, it would expose
#              the whole filesystem.
#   tools    → which of the server's tools to expose to the agent
#              ('*' = all)
MCP_SERVERS = {
    "filesystem": {
        "type": "local",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", WORKDIR],
        "tools": ["*"],
    },
}


def ensure_demo_files() -> None:
    """Create a couple of small files for the agent to read."""
    os.makedirs(WORKDIR, exist_ok=True)
    for name, content in {
        "hello.py": 'print("hello")\n',
        "notes.md": "# Notes\nThis directory is read by the filesystem MCP server.\n",
    }.items():
        path = os.path.join(WORKDIR, name)
        if not os.path.exists(path):
            with open(path, "w") as f:
                f.write(content)


async def main() -> None:
    resume = "--resume" in sys.argv
    ensure_demo_files()

    async with CopilotClient() as client:
        if resume:
            # `resume_session(id, ...)` re-attaches to an existing conversation
            # so the model can refer to anything that was said earlier. We
            # *don't* pass `model=...` here — the original model is reused.
            # MCP servers do need to be re-declared on every resume.
            session_ctx = await client.resume_session(
                SESSION_ID,
                on_permission_request=PermissionHandler.approve_all,
                mcp_servers=MCP_SERVERS,
            )
            prompt = "Based on our earlier chat, which file would you edit to add a feature?"
        else:
            # First-time call: pass our stable `session_id` so we can resume
            # later. Without it the SDK assigns a random UUID and the
            # conversation cannot be retrieved.
            session_ctx = await client.create_session(
                on_permission_request=PermissionHandler.approve_all,
                model="gpt-4.1",
                session_id=SESSION_ID,
                mcp_servers=MCP_SERVERS,
            )
            prompt = f"List the files in {WORKDIR} and summarise each one."

        # Note: `session_ctx` is an async context manager — we entered the
        # client above and the session here, mirroring the pattern in 01.
        async with session_ctx as session:
            # Longer timeout — first invocation also has to `npx`-install
            # the filesystem MCP server which can take a while.
            reply = await session.send_and_wait(prompt, timeout=180)
            if reply:
                print(reply.data.content)

        if not resume:
            print(f"\nSession saved as {SESSION_ID!r}. Re-run with --resume to continue.")


if __name__ == "__main__":
    asyncio.run(main())
