"""
Example 1: Simple Chat — The "Hello World" of the Copilot SDK.

Creates a session and has a back-and-forth conversation with Copilot,
streaming tokens to the console in real time.

Prerequisites:
    pip install github-copilot-sdk
    Copilot CLI installed and signed in (or set COPILOT_GITHUB_TOKEN)

Usage:
    python 01_simple_chat.py
"""

import asyncio

from copilot import CopilotClient, PermissionHandler
from copilot.generated.session_events import SessionEventType


async def main():
    # 1. Create and start the client (auto-manages the CLI process)
    client = CopilotClient()
    await client.start()

    # 2. Open a session with streaming so we see tokens as they arrive
    session = await client.create_session(
        {
            "on_permission_request": PermissionHandler.approve_all,
            "model": "gpt-4.1",
            "streaming": True,
        }
    )

    # 3. Print tokens in real time as the model generates them
    def on_event(event):
        if event.type == SessionEventType.ASSISTANT_MESSAGE_DELTA:
            print(event.data.delta_content, end="", flush=True)

    session.on(on_event)

    # 4. Ask a question and wait for the full response
    print("You: Explain what the GitHub Copilot SDK is in 3 sentences.\n")
    print("Copilot: ", end="")
    await session.send_and_wait({"prompt": "Explain what the GitHub Copilot SDK is in 3 sentences."})
    print("\n")

    # 5. Follow-up question — the session remembers the conversation
    print("You: Now give me a code example in Python.\n")
    print("Copilot: ", end="")
    await session.send_and_wait({"prompt": "Now give me a code example in Python."})
    print("\n")

    # 6. Clean up
    await session.destroy()
    await client.stop()
    print("--- Session ended ---")


if __name__ == "__main__":
    asyncio.run(main())
