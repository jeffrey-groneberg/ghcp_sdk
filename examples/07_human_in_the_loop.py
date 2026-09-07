"""
Example 07 — Human approval and legacy ask_user with SDK 1.0.13.

Run: python examples/07_human_in_the_loop.py
Source: https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/session.py

Interactive teaching adapter, not a production approval UI or sandbox.
Only approve a harmless command after reviewing it; never enter credentials.
"""

import asyncio
import queue
import sys
import threading

from copilot import CopilotClient, PermissionRequestResult
from copilot.rpc import PermissionDecisionApproveOnce, PermissionDecisionReject
from copilot.session import UserInputRequest, UserInputResponse
from copilot.session_events import PermissionRequestShell


INPUT_TIMEOUT = 30
INPUT_LOCK = asyncio.Lock()
INPUT_CLOSED = False


async def read_answer(prompt: str) -> str:
    """Keep the event loop responsive, even when the console has no input."""
    global INPUT_CLOSED
    async with INPUT_LOCK:
        if INPUT_CLOSED:
            raise EOFError("Console input is unavailable; restart the example.")
        answers = queue.Queue()

        def read() -> None:
            try:
                answers.put(input(prompt))
            except (EOFError, OSError) as exc:
                answers.put(exc)

        # A cancelled to_thread(input, ...) can hold asyncio.run() open while
        # its executor waits for stdin. A daemon cannot block process shutdown.
        threading.Thread(target=read, daemon=True).start()
        try:
            async with asyncio.timeout(INPUT_TIMEOUT):
                while answers.empty():
                    await asyncio.sleep(0.05)
            answer = answers.get_nowait()
            if isinstance(answer, Exception):
                raise answer
            return answer.strip()
        except (TimeoutError, EOFError, OSError, asyncio.CancelledError):
            # A timed-out stdin read cannot be killed. Do not start another
            # competing reader; fail closed until the user restarts the script.
            INPUT_CLOSED = True
            raise


async def on_permission_request(request, invocation) -> PermissionRequestResult:
    # Requests are typed variants. In 1.0.13 they also have a string ClassVar
    # `kind`; pattern matching avoids older enum/.value assumptions.
    match request:
        case PermissionRequestShell(full_command_text=command):
            print(f"\n[permission] proposed command:\n{command}")
        case _:
            # File reads can expose secrets too; don't auto-approve them.
            print(f"\n[permission] denied unexpected {type(request).__name__}")
            return PermissionDecisionReject(feedback="Only the reviewed greeting command is in scope.")

    try:
        answer = await read_answer("Approve this one command? [y/N]: ")
    except (EOFError, OSError, TimeoutError):
        print("[permission] input unavailable or timed out; denied.", file=sys.stderr)
        return PermissionDecisionReject(feedback="Human approval was unavailable.")
    if answer.lower() == "y":
        return PermissionDecisionApproveOnce()
    return PermissionDecisionReject(feedback="User rejected the request.")


async def on_user_input_request(
    request: UserInputRequest, invocation,
) -> UserInputResponse:
    choices = request.get("choices") or []
    allow_freeform = request.get("allowFreeform", True)
    print(f"\n[agent asks] {request.get('question', '')}")
    for index, choice in enumerate(choices, 1):
        print(f"  {index}. {choice}")
    if not choices and not allow_freeform:
        raise ValueError("ask_user supplied neither choices nor freeform input.")

    # Bound validation retries as well as each console read.
    for _ in range(3):
        try:
            answer = await read_answer("Your answer (choice number or text): ")
        except (EOFError, OSError, TimeoutError):
            print("[ask_user] input unavailable or timed out.", file=sys.stderr)
            raise
        if choices and answer.isdecimal():
            index = int(answer) - 1
            if 0 <= index < len(choices):
                return {"answer": choices[index], "wasFreeform": False}
        if answer in choices:
            return {"answer": answer, "wasFreeform": False}
        if answer and allow_freeform:
            return {"answer": answer, "wasFreeform": True}
        print("Choose a listed number/text" + (" or enter non-empty text." if allow_freeform else "."))
    raise ValueError("No valid answer after three attempts.")


async def main() -> None:
    async with asyncio.timeout(240):
        async with CopilotClient() as client:
            async with await client.create_session(
                model="gpt-5-mini",
                available_tools=[
                    "builtin:ask_user",
                    "builtin:powershell" if sys.platform == "win32" else "builtin:bash",
                ],
                on_permission_request=on_permission_request,
                # New in 1.0.13: pin the question/answer contract explicitly.
                # "elicitation" instead requires on_elicitation_request.
                ask_user_variant="legacy",
                on_user_input_request=on_user_input_request,
            ) as session:
                reply = await session.send_and_wait(
                    "Use ask_user to ask for my name, allowing freeform input. "
                    "Then request approval for one shell command that prints "
                    "the fixed literal 'Hello from the Copilot SDK.' "
                    "Do not interpolate my name into shell code. "
                    "In your final answer, greet me by name and report the "
                    "actual command result, or say it was denied.",
                    timeout=180,
                )
                if reply is None:
                    raise RuntimeError("Session became idle without an assistant message.")
                print(f"\n[agent] {reply.data.content}")


if __name__ == "__main__":
    asyncio.run(main())
