"""
Example 06: sessions outlive the process that started them (deck slide 25).

Run it twice, as two processes. The first run creates a session with an ID you
choose and asks it to remember a code word. The second run resumes the same ID
in a new process and asks for the word again.

Run:
    python examples/06_session_resume.py create team-assistant-01
    python examples/06_session_resume.py resume team-assistant-01
"""

import asyncio
import sys

from copilot import CopilotClient

PROMPTS = {
    "create": "Remember this code word: AMBER-4711. Reply with OK only.",
    "resume": "What was the code word I gave you earlier? Reply with the word only.",
}


async def main(step: str, session_id: str) -> None:
    async with CopilotClient(mode="coding-agent") as client:  # a new process
        if step == "create":
            session = await client.create_session(
                session_id=session_id, tools={"available_tools": []})
        else:                                     # same ID, after a restart
            session = await client.resume_session(
                session_id, tools={"available_tools": []})
        reply = await session.send_and_wait(PROMPTS[step], timeout=60)
        print(f"{step} {session_id}: {reply.data.content if reply else 'no answer'}")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in PROMPTS:
        sys.exit("usage: python examples/06_session_resume.py create|resume [session-id]")
    asyncio.run(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "team-assistant-01"))
