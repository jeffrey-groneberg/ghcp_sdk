"""
Example 01 — Simple streaming chat

The "hello world" of the GitHub Copilot SDK. We open a session, send a
prompt, and stream the model's reply token-by-token to the console.

Concepts covered:
  * The `CopilotClient` / `CopilotSession` lifecycle (context managers)
  * Permission handlers (required on every session)
  * Event-driven streaming via `session.on(...)`
  * Pattern-matching SDK events with `match` / `case`

Run:
    python examples/01_simple_chat.py
"""

import asyncio

from copilot import CopilotClient

# Typed event payloads. Every event the SDK emits has a `.data` attribute
# that is one of these dataclasses — we use `match`/`case` below to react
# to just the ones we care about.
from copilot.generated.session_events import (
    AssistantMessageDeltaData,  # fired for every streaming chunk
    SessionIdleData,            # fired once when the agent is done talking
)

# Built-in permission handler that auto-approves everything. Good for
# trusted demos; see example 06 for how to write a custom one that asks
# the human for confirmation.
from copilot.session import PermissionHandler


async def main() -> None:
    # `async with CopilotClient()` spawns the bundled Copilot CLI binary
    # as a subprocess (over local stdio JSON-RPC) on enter, and cleanly
    # shuts it down on exit. No manual `start()` / `stop()` calls needed.
    async with CopilotClient() as client:

        # `create_session()` starts a *conversation* with the agent.
        # `await` returns a session context manager — entering it
        # connects to the CLI and exiting cleans up resources.
        #
        # We pick `gpt-4.1` because it's free (multiplier 0) and always
        # available; switch to any model from `await client.list_models()`.
        # `streaming=True` makes the agent emit `AssistantMessageDeltaData`
        # events as it generates text, so we can show progress live.
        async with await client.create_session(
            on_permission_request=PermissionHandler.approve_all,
            model="gpt-4.1",
            streaming=True,
        ) as session:

            # The SDK is fully async / event-driven: `session.send()` returns
            # immediately and the reply arrives over a stream of events.
            # We use an `asyncio.Event` to know when the agent is done so we
            # can fall through to clean shutdown.
            done = asyncio.Event()

            def on_event(event) -> None:
                # `event.data` is a typed dataclass — pattern matching keeps
                # this readable as we add cases. We only handle two events:
                # streaming text and the terminal "idle" signal.
                match event.data:
                    case AssistantMessageDeltaData(delta_content=delta):
                        # Each delta is a small fragment of the response.
                        # `flush=True` makes the terminal show it immediately.
                        print(delta or "", end="", flush=True)
                    case SessionIdleData():
                        # Agent has finished — wake up `main()` so it can exit.
                        done.set()

            # Register the listener. `session.on()` returns an unsubscribe
            # function (ignored here since we're tearing down anyway).
            session.on(on_event)

            # Fire the prompt. `send()` is non-blocking; the model's response
            # arrives via the event stream we registered above.
            await session.send("Explain what the GitHub Copilot SDK is in 3 sentences.")

            # Block until the `SessionIdleData` event fires. Without this the
            # context manager would tear down before the reply was streamed.
            await done.wait()
            print()  # final newline after the streamed text


if __name__ == "__main__":
    asyncio.run(main())
