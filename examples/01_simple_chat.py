"""
Example 01 — Stream a repository-review plan from supplied text, not file reads.

Run: python examples/01_simple_chat.py
Source: https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/session.py
"""

import asyncio

from copilot import CopilotClient
from copilot.session import PermissionHandler
from copilot.session_events import AssistantMessageDeltaData


REVIEW_FILE = "examples/01_simple_chat.py"
REPOSITORY_DESCRIPTION = (
    "This is jeffrey-groneberg/ghcp_sdk, the workshop repository for "
    "'GitHub Copilot SDK - an introduction'. It has eight independently "
    "runnable Python examples using github-copilot-sdk 1.0.13 / runtime 1.0.83. "
    "The selected review file is examples/01_simple_chat.py. Its host creates "
    "a client and session, subscribes to streamed text, waits for a final "
    "message with a deadline, and cleans up its subscription and contexts."
)
REVIEW_PROMPT = (
    f"Supplied repository description:\n{REPOSITORY_DESCRIPTION}\n\n"
    f"Propose a short review plan for {REVIEW_FILE}, focused on "
    "error handling and cleanup. Use only the description above. "
    "You have no file-reading tools: do not claim to have read "
    "the source or found actual bugs. Give three checks to make."
)


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
                available_tools=[],  # This text-only conversation needs no tools.
                streaming=True,
            ) as session:
                saw_delta = False

                def on_event(event) -> None:
                    nonlocal saw_delta
                    match event.data:
                        case AssistantMessageDeltaData(delta_content=delta):
                            saw_delta = saw_delta or bool(delta)
                            print(delta or "", end="", flush=True)

                # Register BEFORE sending so early chunks aren't missed.
                unsubscribe = session.on(on_event)
                try:
                    reply = await session.send_and_wait(REVIEW_PROMPT, timeout=60)
                    if reply is None:
                        raise RuntimeError("Session became idle without an assistant message.")
                    if not saw_delta:
                        print(reply.data.content, end="", flush=True)
                finally:
                    unsubscribe()
                    print()  # Keep the terminal tidy even after partial output.

            # Session exit calls disconnect() -> session.detach in 1.0.13.
            # Persisted state remains; client exit stops its owned CLI process.


if __name__ == "__main__":
    asyncio.run(main())
