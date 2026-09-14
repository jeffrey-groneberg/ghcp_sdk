"""
Slide 05 — The minimal text-only example, as an executable Python file.

Run: python examples/text_only_chat.py
Source: https://github.com/github/copilot-sdk/blob/v1.0.13/python/README.md
"""

import asyncio

from copilot import CopilotClient


async def main() -> None:
    async with asyncio.timeout(180):
        async with CopilotClient() as client:
            async with await client.create_session(
                available_tools=[],
                system_message={
                    "mode": "append",
                    "content": "The SDK means the GitHub Copilot SDK. Explain it directly "
                    "in three sentences; no repository inspection or tool calls are needed.",
                },
            ) as session:
                reply = await session.send_and_wait(
                    "Explain the SDK in 3 sentences.", timeout=60,
                )
                if reply is None:
                    raise RuntimeError("Session became idle without an assistant message.")
                print(reply.data.content)


if __name__ == "__main__":
    asyncio.run(main())
