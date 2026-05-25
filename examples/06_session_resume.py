"""
Example 06 — Session persistence (resume across restarts)

Every Copilot SDK session has a stable ID. Pass the *same* ID to
`create_session()` once and to `resume_session()` later, and the CLI
replays the full conversation history into the model. This is the
primitive behind:

  * Chatbots that "remember" across browser refreshes
  * Background agents that pause overnight and continue tomorrow
  * Multi-process workflows (one process drafts, another reviews)

This demo proves it works:
  1. First run  — tells the model two facts ("my name is Jeffrey, my
                  favourite language is Python") and exits.
  2. --resume   — asks the model to repeat those facts back, WITHOUT
                  re-supplying them. If you see the right name and
                  language, the session was genuinely resumed.

Concepts covered:
  * Choosing a `session_id` (anything stable — UUIDs in real code)
  * `client.resume_session(session_id, ...)`
  * What is and isn't preserved across a resume (handlers, MCP servers,
    and custom tools must always be re-declared; model is reused)

Run:
    python examples/06_session_resume.py            # turn 1 (sets memory)
    python examples/06_session_resume.py --resume   # turn 2 (recalls it)
"""

import asyncio
import sys

from copilot import CopilotClient
from copilot.session import PermissionHandler


# A stable, app-chosen session ID. Production code would derive this from
# the user / conversation in your database; this constant makes the demo
# easy to re-run.
SESSION_ID = "demo-session-resume"


async def main() -> None:
    resume = "--resume" in sys.argv

    async with CopilotClient() as client:
        if resume:
            # `resume_session(id, ...)` re-attaches to an existing
            # conversation so the model can refer to anything that was
            # said earlier. Note: we do NOT pass `model=...` here — the
            # original model is reused.
            session_ctx = await client.resume_session(
                SESSION_ID,
                on_permission_request=PermissionHandler.approve_all,
            )
            prompt = (
                "Without re-reading my earlier message, what did I tell you "
                "my name is and which programming language I prefer?"
            )
        else:
            # First call: pass our stable `session_id` so we can resume
            # later. Without it the SDK assigns a random UUID and the
            # conversation cannot be retrieved.
            session_ctx = await client.create_session(
                on_permission_request=PermissionHandler.approve_all,
                model="gpt-4.1",
                session_id=SESSION_ID,
            )
            prompt = (
                "Please remember the following two facts for the rest of our "
                "conversation: my name is Jeffrey, and my favourite "
                "programming language is Python. Just acknowledge that you "
                "have noted them — no need to repeat them back."
            )

        async with session_ctx as session:
            reply = await session.send_and_wait(prompt, timeout=60)
            if reply:
                print(reply.data.content)

        if not resume:
            print(
                f"\nSession saved as {SESSION_ID!r}. "
                "Re-run with --resume to continue the conversation."
            )


if __name__ == "__main__":
    asyncio.run(main())
