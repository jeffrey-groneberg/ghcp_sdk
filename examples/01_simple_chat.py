"""
Example 01: your first app (deck slide 17).

One question, one answer. The client declares its mode, which SDK 2.0 requires,
and the session's tool allow-list is empty, so it is text only.

Run: python examples/01_simple_chat.py
"""

import asyncio

from copilot import CopilotClient


async def main() -> None:
    async with CopilotClient(mode="coding-agent") as client:
        async with await client.create_session(
            tools={"available_tools": []},  # text only: no tools this time
        ) as session:
            reply = await session.send_and_wait(
                "In one sentence: what is an agent harness?", timeout=60)
            print(reply.data.content if reply else "no answer")


if __name__ == "__main__":
    asyncio.run(main())
