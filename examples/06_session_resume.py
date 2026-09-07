"""
Example 06 — Resume a persisted conversation with SDK 1.0.13.

Run from the same machine/account and CLI state directory:
    python examples/06_session_resume.py
    python examples/06_session_resume.py --resume

Source: https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/client.py
"""

import argparse
import asyncio

from copilot import CopilotClient
from copilot.session import PermissionHandler


# Use a unique ID for each real conversation. This default is a workshop aid,
# not an authorization boundary or a multi-user session naming strategy.
SESSION_ID = "demo-session-resume"


async def main(resume: bool = False, session_id: str = SESSION_ID) -> None:
    async with asyncio.timeout(180):
        async with CopilotClient() as client:
            if resume:
                # Re-register callbacks and the tool policy on cold resume.
                # model= is supported, but omitting it keeps the existing model.
                session_ctx = await client.resume_session(
                    session_id,
                    on_permission_request=PermissionHandler.approve_all,
                    available_tools=[],
                )
                prompt = (
                    "Using our earlier conversation, what did I tell you my name "
                    "is and which programming language I prefer?"
                )
            else:
                # Omitting session_id also works: save session.session_id, or
                # discover it later through await client.list_sessions().
                session_ctx = await client.create_session(
                    on_permission_request=PermissionHandler.approve_all,
                    model="gpt-5-mini",
                    session_id=session_id,
                    available_tools=[],  # Recall must not read this source file.
                )
                prompt = (
                    "Please remember two facts for our conversation: my name "
                    "is Jeffrey, and my favourite programming language is Python. "
                    "Just acknowledge that you have noted them."
                )

            async with session_ctx as session:
                print(f"Session ID: {session.session_id}")
                reply = await session.send_and_wait(prompt, timeout=60)
                if reply is None:
                    raise RuntimeError("Session became idle without an assistant message.")
                print(reply.data.content)

            # disconnect() detaches; it does not delete persisted conversation.
            if not resume:
                print(
                    f"\nDetached from {session_id!r}; persisted state is retained. "
                    "Run again with --resume and the same --session-id."
                )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--session-id", default=SESSION_ID)
    args = parser.parse_args()
    asyncio.run(main(args.resume, args.session_id))
