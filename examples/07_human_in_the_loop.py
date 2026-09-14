"""
Example 07 — Structured human input and explicit permission approval.

Run: python examples/07_human_in_the_loop.py
Source: https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/session.py

Interactive teaching adapter, not a production approval UI or sandbox.
It accepts one expected name form and one exact harmless shell command.
"""

import asyncio
import shlex
import sys

from copilot import CopilotClient, PermissionRequestResult, ToolSet
from copilot.rpc import (
    PermissionDecisionApproveOnce,
    PermissionDecisionReject,
    PermissionDecisionUserNotAvailable,
)
from copilot.session import (
    ElicitationContext,
    ElicitationResult,
    UserInputRequest,
    UserInputResponse,
)
from copilot.session_events import (
    PermissionRequestShell,
    ToolExecutionCompleteData,
    ToolExecutionStartData,
)

from _console_input import read_answer


INPUT_TIMEOUT = 120
MAX_NAME_LENGTH = 80
SHELL_TOOL = "powershell" if sys.platform == "win32" else "bash"
EXPECTED_COMMAND = (
    "Write-Output 'Hello from the Copilot SDK.'"
    if sys.platform == "win32"
    else "printf '%s\\n' 'Hello from the Copilot SDK.'"
)


def is_expected_command(command: str) -> bool:
    if sys.platform == "win32":
        return command.strip() == EXPECTED_COMMAND
    try:
        return shlex.split(command) == [
            "printf",
            "%s\\n",
            "Hello from the Copilot SDK.",
        ]
    except ValueError:
        return False


async def on_permission_request(request, invocation) -> PermissionRequestResult:
    match request:
        case PermissionRequestShell(full_command_text=command):
            print(f"\n[permission] proposed command:\n{command}")
            if request.request_sandbox_bypass is True:
                return PermissionDecisionReject(
                    feedback="Sandbox bypass is outside this example's scope."
                )
            if not is_expected_command(command):
                print("[permission] denied: command is outside the allowlist.")
                return PermissionDecisionReject(
                    feedback="Only the exact fixed greeting command is allowed."
                )
        case _:
            return PermissionDecisionReject(
                feedback="Only the reviewed greeting command is in scope."
            )

    if request.warning:
        print(f"[permission warning] {request.warning}")
    if request.managed_approval_required is True:
        print("[permission] managed policy requires an explicit human decision.")
    try:
        answer = await read_answer(
            "Approve this one exact command? [y/N]: ",
            timeout=INPUT_TIMEOUT,
        )
    except (EOFError, OSError, TimeoutError):
        print("[permission] input unavailable or timed out; denied.", file=sys.stderr)
        return PermissionDecisionUserNotAvailable()
    if answer.lower() == "y":
        return PermissionDecisionApproveOnce()
    return PermissionDecisionReject(feedback="User rejected the request.")


async def on_elicitation_request(context: ElicitationContext) -> ElicitationResult:
    if context.get("mode", "form") != "form":
        return {"action": "decline"}

    schema = context.get("requestedSchema")
    properties = schema.get("properties") if isinstance(schema, dict) else None
    required = schema.get("required") if isinstance(schema, dict) else None
    name_schema = properties.get("name") if isinstance(properties, dict) else None
    expected_schema = (
        schema.get("type") == "object"
        and set(properties) == {"name"}
        and isinstance(required, list)
        and set(required) == {"name"}
        and isinstance(name_schema, dict)
        and name_schema.get("type") == "string"
    ) if isinstance(schema, dict) and isinstance(properties, dict) else False
    if not expected_schema:
        print("[elicitation] declined an unexpected form schema.", file=sys.stderr)
        return {"action": "decline"}

    print(f"\n[agent asks] {context.get('message', 'What is your name?')}")
    for _ in range(3):
        try:
            answer = await read_answer("Your name: ", timeout=INPUT_TIMEOUT)
        except (EOFError, OSError, TimeoutError):
            print("[elicitation] input unavailable or timed out.", file=sys.stderr)
            return {"action": "cancel"}
        if 1 <= len(answer) <= MAX_NAME_LENGTH:
            return {"action": "accept", "content": {"name": answer}}
        print(f"Enter between 1 and {MAX_NAME_LENGTH} characters.")
    return {"action": "cancel"}


async def on_user_input_request(
    request: UserInputRequest,
    invocation,
) -> UserInputResponse:
    choices = request.get("choices") or []
    if choices or request.get("allowFreeform", True) is not True:
        raise ValueError("This fallback accepts one freeform name and no choices.")

    print(f"\n[agent asks] {request.get('question', 'What is your name?')}")
    for _ in range(3):
        answer = await read_answer("Your name: ", timeout=INPUT_TIMEOUT)
        if 1 <= len(answer) <= MAX_NAME_LENGTH:
            return {"answer": answer, "wasFreeform": True}
        print(f"Enter between 1 and {MAX_NAME_LENGTH} characters.")
    raise ValueError("No valid name after three attempts.")


async def has_structured_ask_user(session) -> bool:
    """Check the runtime catalogue rather than trusting the SDK option alone."""
    await session.rpc.tools.initialize_and_validate()
    metadata = await session.rpc.tools.get_current_metadata()
    for tool in metadata.tools or []:
        if tool.name != "ask_user":
            continue
        schema = tool.input_schema if isinstance(tool.input_schema, dict) else {}
        properties = schema.get("properties") or {}
        return "message" in properties and "requestedSchema" in properties
    return False


async def run_conversation(session, prompt: str) -> None:
    def on_event(event) -> None:
        match event.data:
            case ToolExecutionStartData(tool_name=name):
                print(f"[tool] {name} started")
            case ToolExecutionCompleteData(success=False, error=error):
                message = getattr(error, "message", None) or str(error)
                print(f"[tool] failed: {message}", file=sys.stderr)

    unsubscribe = session.on(on_event)
    try:
        reply = await session.send_and_wait(prompt, timeout=180)
        if reply is None:
            raise RuntimeError("Session became idle without an assistant message.")
        print(f"\n[agent] {reply.data.content}")
    finally:
        unsubscribe()


async def main() -> None:
    async with asyncio.timeout(240):
        async with CopilotClient() as client:
            tools = ToolSet().add_builtin(["ask_user", SHELL_TOOL])
            async with await client.create_session(
                available_tools=tools,
                on_permission_request=on_permission_request,
                ask_user_variant="elicitation",
                on_elicitation_request=on_elicitation_request,
            ) as session:
                if await has_structured_ask_user(session):
                    await run_conversation(
                        session,
                        "Use ask_user exactly once with message 'What is your name?' "
                        "and a requestedSchema object containing one required string "
                        f"property named 'name'. After the answer, call the {SHELL_TOOL} "
                        "tool with exactly the following command and no other command:\n"
                        f"{EXPECTED_COMMAND}\nDo not use ask_user for command approval; "
                        "the runtime permission callback handles that separately. Do "
                        "not interpolate the name into shell code. In your final answer, "
                        "greet the person by name and report the actual command result, "
                        "or say it was denied.",
                    )
                    return

            print(
                "[hitl] Structured ask_user is unavailable in this runtime; "
                "falling back to the legacy question contract."
            )
            async with await client.create_session(
                available_tools=tools,
                on_permission_request=on_permission_request,
                ask_user_variant="legacy",
                on_user_input_request=on_user_input_request,
            ) as session:
                await run_conversation(
                    session,
                    "Use ask_user exactly once to ask 'What is your name?', with "
                    f"freeform input enabled and no choices. After the answer, call the "
                    f"{SHELL_TOOL} tool with exactly the following command and no other "
                    f"command:\n{EXPECTED_COMMAND}\nDo not use ask_user for command "
                    "approval; the runtime permission callback handles that separately. "
                    "Do not interpolate the name into shell code. In your final answer, "
                    "greet the person by name and report the actual command result, or "
                    "say it was denied.",
                )


if __name__ == "__main__":
    asyncio.run(main())
