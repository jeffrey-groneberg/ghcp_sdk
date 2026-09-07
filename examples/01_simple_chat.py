"""
Example 01 — Streaming chat with GitHub Copilot SDK 1.0.13.

Run: python examples/01_simple_chat.py
Source: https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/session.py
"""

import asyncio

from copilot import CopilotClient
from copilot.session import PermissionHandler
from copilot.session_events import AssistantMessageDeltaData


async def main() -> None:
    # Bound startup, the conversation, and normal shutdown as a whole.
    async with asyncio.timeout(180):
        # New in 1.0.13: optional application identity on server.connect.
        # These describe THIS app, not the model or your GitHub credentials.
        async with CopilotClient(
            client_info={
                "application_name": "ghcp-sdk-examples",
                "application_version": "0.1.0",
                "integration_name": "python-workshop",
                "integration_version": "1.0.13",
            },
        ) as client:
            async with await client.create_session(
                # Auto-approval is for trusted demos, not a security sandbox.
                on_permission_request=PermissionHandler.approve_all,
                model="gpt-5-mini",
                available_tools=[],  # This text-only conversation needs no tools.
                streaming=True,
            ) as session:
                def on_event(event) -> None:
                    match event.data:
                        case AssistantMessageDeltaData(delta_content=delta):
                            print(delta or "", end="", flush=True)

                # Register BEFORE sending so early chunks aren't missed.
                unsubscribe = session.on(on_event)
                try:
                    # Streaming events still arrive while this helper waits.
                    # It handles session.error and raises TimeoutError on expiry;
                    # a hand-written idle Event alone could wait forever.
                    reply = await session.send_and_wait(
                        "Explain what the GitHub Copilot SDK is in 3 sentences.",
                        timeout=60,
                    )
                    if reply is None:
                        raise RuntimeError("Session became idle without an assistant message.")
                finally:
                    unsubscribe()
                    print()  # Keep the terminal tidy even after partial output.

            # Session exit calls disconnect() -> session.detach in 1.0.13.
            # Persisted state remains; client exit stops its owned CLI process.


if __name__ == "__main__":
    asyncio.run(main())
