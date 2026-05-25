"""
Example 06 — Human in the loop (permissions + ask_user)

Two callbacks let your app stay in control of the agent:

  1. `on_permission_request` — fires *before* the agent runs anything that
     touches the user's machine (shell commands, file writes, MCP servers,
     network calls, ...). You return an approval/denial.
  2. `on_user_input_request` — fires when the agent calls the built-in
     `ask_user` tool to gather information from the human.

Both replace what the official Copilot CLI normally does interactively, which
makes the SDK ideal for headless apps, custom UIs, IDE extensions, etc.

Run:  python examples/06_human_in_the_loop.py
"""

import asyncio

from copilot import CopilotClient
from copilot.session import PermissionRequestResult
from copilot.generated.session_events import (
    AssistantMessageData,
    SessionIdleData,
)


# --- Permission handler ------------------------------------------------------
#
# The SDK calls this for *every* sensitive action the agent wants to take.
# `request.kind` is one of: 'shell', 'write', 'read', 'mcp', 'url', 'memory',
# 'custom-tool', 'hook'. `request` also exposes useful context such as
# `command`, `path`, `intention`, `risk`, etc., so you can decide based on
# what the agent is trying to do.
#
# Return a `PermissionRequestResult(kind=...)` where kind is one of:
#   "approve-once"       → allow this single call
#   "reject"             → block (the agent will see this and pick another path)
#   "user-not-available" → no human around; let the SDK use its default policy
#   "no-result"          → defer (rarely needed)
#
# `PermissionHandler.approve_all` in the SDK is literally one line:
#   return PermissionRequestResult(kind="approve-once")
def on_permission_request(request, invocation) -> PermissionRequestResult:
    kind = request.kind.value  # enum → str, e.g. "read"

    # Reads are safe (listing dirs, viewing files): auto-approve.
    if kind == "read":
        return PermissionRequestResult(kind="approve-once")

    # Anything else (shell, write, network, ...) goes to the human.
    # `input()` here is just for the demo; a real app would surface a UI
    # prompt, a Slack message, etc.
    print(f"\n[permission] agent wants: {kind} — {getattr(request, 'intention', '')}")
    answer = input("approve? [y/N]: ").strip().lower()
    if answer == "y":
        return PermissionRequestResult(kind="approve-once")
    return PermissionRequestResult(kind="reject")


# --- ask_user handler --------------------------------------------------------
#
# When the agent calls its built-in `ask_user` tool, the SDK forwards the
# question here instead of prompting on the CLI. The handler receives a
# `UserInputRequest` (TypedDict with `question`, `choices`, `allowFreeform`)
# and must return a `UserInputResponse` (`{"answer": str, "wasFreeform": bool}`).
def on_user_input_request(request, invocation) -> dict:
    question = request.get("question", "")
    choices = request.get("choices") or []
    print(f"\n[agent asks] {question}")
    if choices:
        for i, c in enumerate(choices, 1):
            print(f"  {i}. {c}")
    answer = input("your answer: ").strip()
    # `wasFreeform=True` tells the agent the user typed their own text rather
    # than picking one of the supplied `choices`.
    return {"answer": answer, "wasFreeform": True}


async def main() -> None:
    # The two handlers above are wired up via `create_session` kwargs.
    # `request_user_input=True` activates the ask_user callback path.
    async with CopilotClient() as client:
        async with await client.create_session(
            model="gpt-4.1",
            on_permission_request=on_permission_request,
            on_user_input_request=on_user_input_request,
        ) as session:
            done = asyncio.Event()

            def on_event(event):
                # Print final assistant turns and stop on idle. We use the
                # non-streaming `AssistantMessageData` here because it's enough
                # for a short demo; see example 01 for token-by-token streaming.
                match event.data:
                    case AssistantMessageData(content=content):
                        print(f"\n[agent] {content}\n")
                    case SessionIdleData():
                        done.set()

            session.on(on_event)

            # This prompt is designed to trigger BOTH callbacks:
            #   - ask_user → to learn the human's name
            #   - permission(shell) → to actually run a command that uses it
            await session.send(
                "Use the ask_user tool to ask me for my name. "
                "Then run a single shell command that prints "
                "'Hello, <name>! Welcome to the Copilot SDK.' "
                "Reply with the command's output."
            )
            await done.wait()


if __name__ == "__main__":
    asyncio.run(main())
