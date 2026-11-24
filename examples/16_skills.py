"""
Example 16: skills, reusable instructions the agent loads on demand.

A skill is a folder with a SKILL.md file. This session loads the skills in
examples/skills, and the agent uses pr-description when you ask for a pull
request description. The skill.invoked event shows when it does.

Run: python examples/16_skills.py
"""

import asyncio
from pathlib import Path

from copilot import CopilotClient
from copilot.session_events import SkillInvokedData

SKILLS = Path(__file__).parent / "skills"


def on_event(event):
    match event.data:
        case SkillInvokedData(name=name):
            print(f"[skill] {name} invoked")


async def main() -> None:
    async with CopilotClient(mode="coding-agent") as client:
        session = await client.create_session(
            skills={"directories": [str(SKILLS)]},
            tools={"available_tools": ["builtin:skill"]},  # the tool that loads a skill
            events={"on_event": on_event})
        reply = await session.send_and_wait(
            "Write the pull request description for this change: add() in calc.py "
            "returned a - b and now returns a + b; test_add passes.", timeout=120)
        print(reply.data.content if reply else "no answer")


if __name__ == "__main__":
    asyncio.run(main())
