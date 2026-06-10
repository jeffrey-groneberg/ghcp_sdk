"""
Example 07 — Human in the loop (permissions + ask_user)

Two callbacks let your app stay in control of the agent:

  1. `on_permission_request` — fires *before* the agent runs anything that
     touches the user's machine (shell commands, file writes, MCP servers,
     network calls, ...). You return an approval/denial.
  2. `on_user_input_request` — fires when the agent calls the built-in
     `ask_user` tool to gather information from the human.

Both replace what the official Copilot CLI normally does interactively, which
makes the SDK ideal for headless apps, custom UIs, IDE extensions, etc.

Run:  python examples/07_human_in_the_loop.py
"""

import asyncio

from copilot import CopilotClient, PermissionRequestResult
from copilot.rpc import PermissionDecisionApproveOnce, PermissionDecisionReject
from copilot.session_events import (
    AssistantMessageData,
    SessionIdleData,
    # `PermissionRequest` is a *discriminated union* of one class per kind.
    # Import the variants we want to react to and pattern-match on them.
    PermissionRequestRead,
    PermissionRequestShell,
    PermissionRequestWrite,
)


# --- Permission handler ------------------------------------------------------
#
# The SDK calls this for *every* sensitive action the agent wants to take.
# `request` is a discriminated union — one dataclass per kind
# (`PermissionRequestShell`, `PermissionRequestWrite`, `PermissionRequestRead`,
# `PermissionRequestMcp`, ...) — so we `match`/`case` on the variant to read
# its per-kind fields (`full_command_text`, `file_name`, `path`, `intention`).
#
# Return one of the permission-decision objects from `copilot.rpc`:
#   PermissionDecisionApproveOnce()           → allow this single call
#   PermissionDecisionReject(feedback="...")  → block; the agent sees the
#                                               feedback and can pick another path
#   PermissionDecisionUserNotAvailable()      → no human around; SDK default policy
#
# `PermissionHandler.approve_all` in the SDK is literally one line:
#   return PermissionDecisionApproveOnce()
def on_permission_request(request, invocation) -> PermissionRequestResult:
    match request:
        # Reads are safe (listing dirs, viewing files): auto-approve.
        case PermissionRequestRead():
            return PermissionDecisionApproveOnce()
        case PermissionRequestShell(full_command_text=cmd):
            detail = f"run shell command: {cmd}"
        case PermissionRequestWrite(file_name=name):
            detail = f"write file: {name}"
        case _:
            detail = getattr(request, "intention", type(request).__name__)

    # Anything that isn't a plain read goes to the human. `input()` here is
    # just for the demo; a real app would surface a UI prompt, a Slack
    # message, etc.
    print(f"\n[permission] agent wants to {detail}")
    answer = input("approve? [y/N]: ").strip().lower()
    if answer == "y":
        return PermissionDecisionApproveOnce()
    return PermissionDecisionReject(feedback="User rejected the request.")


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
    # Passing `on_user_input_request` is what activates the ask_user path.
    async with CopilotClient() as client:
        async with await client.create_session(
            model="gpt-5-mini",
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
