"""
Example 5: MCP Servers + Session Persistence — Connect external tools
and resume conversations across restarts.

Connects a local MCP server (filesystem access) so Copilot can browse
a directory.  Uses a stable session ID so the session can be resumed
later with full conversation history.

Prerequisites:
    pip install github-copilot-sdk
    npm install -g @modelcontextprotocol/server-filesystem   (for the MCP server)
    Copilot CLI installed and signed in (or set COPILOT_GITHUB_TOKEN)

Usage:
    python 05_mcp_and_persistence.py              # first run: creates session
    python 05_mcp_and_persistence.py --resume      # later: resumes the same session
"""

import asyncio
import os
import sys
import tempfile

from copilot import CopilotClient, PermissionHandler
from copilot.generated.session_events import SessionEventType

SESSION_ID = "demo-mcp-persistent-session"
ALLOWED_DIR = os.path.join(tempfile.gettempdir(), "copilot-demo")


async def ensure_demo_directory():
    """Create a small demo directory for the filesystem MCP server to browse."""
    os.makedirs(ALLOWED_DIR, exist_ok=True)

    files = {
        "hello.py": 'print("Hello from Copilot SDK!")\n',
        "config.json": '{\n  "app_name": "MCP Demo",\n  "version": "1.0.0"\n}\n',
        "notes.md": (
            "# Notes\n\n"
            "- The Copilot SDK supports MCP servers\n"
            "- Both local (stdio) and remote (HTTP) types\n"
            "- This demo uses the filesystem MCP server\n"
        ),
    }
    for name, content in files.items():
        path = os.path.join(ALLOWED_DIR, name)
        if not os.path.exists(path):
            with open(path, "w") as f:
                f.write(content)
    print(f"📁 Demo directory ready: {ALLOWED_DIR}")


async def create_new_session(client):
    """Create a brand-new session with an MCP filesystem server attached."""
    print(f"🆕 Creating new session: {SESSION_ID}\n")

    session = await client.create_session(
        {
            "on_permission_request": PermissionHandler.approve_all,
            "model": "gpt-4.1",
            "streaming": True,
            "session_id": SESSION_ID,
            "mcp_servers": {
                # Local MCP server: runs as a subprocess, communicates over stdin/stdout
                "filesystem": {
                    "type": "local",
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", ALLOWED_DIR],
                    "tools": ["*"],  # Enable all tools the server provides
                },
            },
        }
    )
    return session


async def resume_existing_session(client):
    """Resume a previously created session — full conversation history is restored."""
    print(f"🔄 Resuming session: {SESSION_ID}\n")

    session = await client.resume_session(
        SESSION_ID,
        {
            "on_permission_request": PermissionHandler.approve_all,
            "mcp_servers": {
                "filesystem": {
                    "type": "local",
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", ALLOWED_DIR],
                    "tools": ["*"],
                },
            },
        },
    )
    return session


async def main():
    resume_mode = "--resume" in sys.argv

    await ensure_demo_directory()

    client = CopilotClient()
    await client.start()

    # Create or resume the session
    if resume_mode:
        session = await resume_existing_session(client)
    else:
        session = await create_new_session(client)

    # Stream output to the console
    def on_event(event):
        if event.type == SessionEventType.ASSISTANT_MESSAGE_DELTA:
            print(event.data.delta_content, end="", flush=True)

    session.on(on_event)

    if not resume_mode:
        # First run: ask Copilot to explore the directory via the MCP server
        prompt = f"List the files in {ALLOWED_DIR} and summarize what each one contains."
        print(f"You: {prompt}\n")
        print("Copilot: ", end="")
        await session.send_and_wait(prompt)
        print("\n")

        print("💾 Session persisted! Run again with --resume to continue.\n")
    else:
        # Resume: ask a follow-up — Copilot remembers the previous conversation
        prompt = "Based on our earlier conversation, which file would you modify to add a new feature?"
        print(f"You: {prompt}\n")
        print("Copilot: ", end="")
        await session.send_and_wait(prompt)
        print("\n")

    await session.disconnect()
    await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
