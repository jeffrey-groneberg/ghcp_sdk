"""
Example 07 — Choose a review focus, then approve or deny one fixed test command.

Run: python examples/07_human_in_the_loop.py
Source: https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/session.py

An introductory terminal adapter, not a production authorization UI or sandbox.
The focus never becomes shell code. Only the host verifies decisions/results.
"""

import asyncio
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import sys

from copilot import CopilotClient, PermissionRequestResult, ToolSet
from copilot.rpc import (
    PermissionDecisionApproveOnce,
    PermissionDecisionReject,
    PermissionDecisionUserNotAvailable,
)
from copilot.session import ElicitationContext, ElicitationResult, UserInputRequest, UserInputResponse
from copilot.session_events import (
    PermissionRequestShell,
    ToolExecutionCompleteData,
    ToolExecutionStartData,
)

from _console_input import read_answer
from _tool_trace import ToolTrace


REPO_ROOT = Path(__file__).resolve().parents[1]
REVIEW_FILE = "examples/01_simple_chat.py"
INPUT_TIMEOUT = 120
FOCUSES = ("errors", "cleanup")
FOCUS_SCHEMA = {
    "type": "object",
    "properties": {"focus": {"type": "string", "enum": list(FOCUSES)}},
    "required": ["focus"],
    "additionalProperties": False,
}
SHELL_TOOL = "powershell" if sys.platform == "win32" else "bash"
EXPECTED_COMMAND = "python -m unittest discover -s examples/tests -v"


def validate_focus(answer: str) -> str:
    if not isinstance(answer, str) or answer.strip().lower() not in FOCUSES:
        raise ValueError("Review focus must be 'errors' or 'cleanup'.")
    return answer.strip().lower()


def is_focus_form(context: ElicitationContext) -> bool:
    schema = context.get("requestedSchema")
    if context.get("mode", "form") != "form" or not isinstance(schema, dict):
        return False
    properties = schema.get("properties")
    if not isinstance(properties, dict) or set(properties) != {"focus"}:
        return False
    focus = properties["focus"]
    return (
        schema.get("type") == "object"
        and schema.get("required") == ["focus"]
        and schema.get("additionalProperties", False) is False
        and isinstance(focus, dict)
        and focus.get("type") == "string"
        and set(focus) <= {"type", "enum", "title", "description"}
        and focus.get("enum", list(FOCUSES)) == list(FOCUSES)
    )


def is_expected_command(command: str) -> bool:
    # Token splitting alone is not a shell-safety check (substitutions/operators).
    return (
        isinstance(command, str)
        and not any(char in command for char in ";&|<>`$\\\r\n")
        and command == EXPECTED_COMMAND
    )


def is_safe_shell_args(arguments: object) -> bool:
    return (
        isinstance(arguments, dict)
        and set(arguments) <= {"command", "description", "mode", "initial_wait"}
        and is_expected_command(arguments.get("command"))
        and arguments.get("mode", "sync") == "sync"
        and arguments.get("initial_wait", 120) == 120
    )


def unittest_reported_ok(content: str) -> bool:
    summaries = re.findall(
        r"(?m)^Ran (\d+) tests? in [^\r\n]+\r?\n\r?\n"
        r"(OK(?: \([^\r\n]*\))?|FAILED[^\r\n]*)\r?$",
        content,
    )
    return bool(summaries and int(summaries[-1][0]) > 0 and summaries[-1][1].startswith("OK"))


@dataclass
class ReviewHost:
    focus: str | None = None
    input_requested: bool = False
    decision: str | None = None
    decision_call_id: str | None = None
    trace: ToolTrace = field(default_factory=ToolTrace)

    async def collect_focus(self) -> str:
        if self.input_requested:
            raise ValueError("Only one review-focus request is allowed.")
        self.input_requested = True
        for _ in range(3):
            answer = await read_answer("Review focus [errors/cleanup]: ", timeout=INPUT_TIMEOUT)
            try:
                self.focus = validate_focus(answer)
                print(f"[hitl] focus accepted: {self.focus}")
                return self.focus
            except ValueError:
                print("Enter 'errors' or 'cleanup'.")
        raise ValueError("No valid review focus after three attempts.")

    async def on_elicitation_request(self, context: ElicitationContext) -> ElicitationResult:
        if not is_focus_form(context):
            print("[elicitation] declined an unexpected form schema.", file=sys.stderr)
            return {"action": "decline"}
        try:
            focus = await self.collect_focus()
        except (EOFError, OSError, TimeoutError, ValueError):
            print("[elicitation] cancelled: no valid review focus.", file=sys.stderr)
            return {"action": "cancel"}
        return {"action": "accept", "content": {"focus": focus}}

    async def on_user_input_request(
        self, request: UserInputRequest, invocation,
    ) -> UserInputResponse:
        if request.get("choices") or request.get("allowFreeform", True) is not True:
            raise ValueError("This fallback accepts one freeform review focus and no choices.")
        try:
            focus = await self.collect_focus()
        except (EOFError, OSError, TimeoutError):
            raise RuntimeError("Review focus input unavailable or timed out.") from None
        return {"answer": focus, "wasFreeform": True}

    async def on_pre_tool_use(self, input_data, invocation):
        if input_data["toolName"] == "ask_user":
            return None
        if (
            input_data["toolName"] != SHELL_TOOL
            or input_data.get("workingDirectory") != str(REPO_ROOT)
            or not is_safe_shell_args(input_data.get("toolArgs"))
            or self.focus not in FOCUSES
        ):
            print("[hitl hook] denied: only the fixed command in the repository root is allowed.")
            return {
                "permissionDecision": "deny",
                "permissionDecisionReason": "Choose a valid focus, then use only the fixed command.",
            }
        # Keep the normal typed shell permission request. "ask" would create
        # a separate hook permission request, not PermissionRequestShell.
        return None

    async def on_permission_request(self, request, invocation) -> PermissionRequestResult:
        call_id = getattr(request, "tool_call_id", None)
        if (
            not isinstance(request, PermissionRequestShell)
            or not call_id
            or not is_expected_command(request.full_command_text)
            or request.has_write_file_redirection
            or request.possible_urls
            or request.request_sandbox_bypass is True
            or self.focus not in FOCUSES
            or self.decision_call_id is not None
        ):
            print(f"[host] COMMAND_DENIED id={call_id or 'missing'} reason=outside the one-command policy")
            return PermissionDecisionReject(feedback="Only one correlated fixed test command is allowed.")

        self.decision_call_id = call_id
        print(f"[permission] proposed command (id={call_id}): {EXPECTED_COMMAND}")
        print(f"[permission] working directory: {REPO_ROOT}")
        if request.warning:
            print(f"[permission warning] {request.warning}")
        if request.managed_approval_required is True:
            print("[permission] managed policy requires an explicit human decision.")
        try:
            answer = await read_answer("Approve this one exact command? [y/N]: ", timeout=INPUT_TIMEOUT)
        except (EOFError, OSError, TimeoutError):
            self.decision = "unavailable"
            print(f"[host] COMMAND_DENIED id={call_id} reason=input unavailable or timed out")
            return PermissionDecisionUserNotAvailable()
        if answer.lower() == "y":
            self.decision = "approve-once"
            print(f"[host] COMMAND_APPROVE_ONCE id={call_id}")
            return PermissionDecisionApproveOnce()
        self.decision = "reject"
        print(f"[host] COMMAND_DENIED id={call_id} reason=user rejected")
        return PermissionDecisionReject(feedback="User rejected the request.")

    def on_event(self, event) -> None:
        self.trace.record(event.data)
        match event.data:
            case ToolExecutionStartData(tool_name=name, tool_call_id=call_id):
                print(f"[tool] {name} started id={call_id}")
            case ToolExecutionCompleteData(tool_call_id=call_id, success=success, error=error):
                print(f"[tool] completed id={call_id} success={success}")
                if error is not None:
                    print(f"[tool] failed: {error.message}", file=sys.stderr)

    def report_outcome(self) -> None:
        call_id = self.decision_call_id
        start = self.trace.started.get(call_id)
        completion = self.trace.completed.get(call_id)
        if self.focus not in FOCUSES or self.decision is None:
            raise RuntimeError("A validated focus and a host command decision are required.")
        if (
            start is None or start.tool_name != SHELL_TOOL
            or not is_safe_shell_args(start.arguments) or completion is None
        ):
            raise RuntimeError("Missing matching fixed-command start/completion evidence.")
        for other_id, other in self.trace.started.items():
            if other.tool_name == SHELL_TOOL and self.trace.successful_content(other_id) is not None:
                if other_id != call_id or self.decision != "approve-once":
                    raise RuntimeError("A successful shell result has no matching host approval.")
        if self.decision != "approve-once":
            if completion.success:
                raise RuntimeError("The denied command reported success; execution is unverified.")
            print(f"[host] COMMAND_DENIAL_RECORDED id={call_id}; no execution claimed")
            return
        content = self.trace.successful_content(call_id)
        if content is not None:
            print(f"[command result]\n{content}")
        if content is None or not unittest_reported_ok(content):
            raise RuntimeError("Matching command result did not report a completed passing unittest run.")
        print(f"[host] COMMAND_RESULT_VERIFIED id={call_id}; unittest reported OK")


async def has_structured_ask_user(session) -> bool:
    await session.rpc.tools.initialize_and_validate()
    metadata = await session.rpc.tools.get_current_metadata()
    for tool in metadata.tools or []:
        if tool.name == "ask_user":
            schema = tool.input_schema if isinstance(tool.input_schema, dict) else {}
            properties = schema.get("properties")
            return isinstance(properties, dict) and {"message", "requestedSchema"} <= set(properties)
    return False


async def run_conversation(session, host: ReviewHost, structured: bool) -> None:
    question = (
        "Use ask_user exactly once with message 'Choose a review focus: errors or cleanup' "
        f"and this requestedSchema: {json.dumps(FOCUS_SCHEMA)}. "
        if structured else
        "Use ask_user exactly once to ask 'Choose a review focus: errors or cleanup', "
        "with freeform input enabled and no choices. "
    )
    prompt = (
        f"We are reviewing {REVIEW_FILE} in this workshop repository. "
        + question
        + f"After receiving a valid focus, request the {SHELL_TOOL} tool with "
        f"command={EXPECTED_COMMAND!r}, mode='sync', initial_wait=120, and a short "
        "description. Use no shellId, no other arguments or commands, and no "
        "sandbox bypass. The session working directory is the repository root. "
        "Never interpolate the focus into shell code. Do not ask ask_user for "
        "command approval: the permission callback handles that. Your final "
        "message should acknowledge the review focus only; the host reports the "
        "actual permission decision and test result. Do not claim to have read source."
    )
    unsubscribe = session.on(host.on_event)
    try:
        reply = await session.send_and_wait(prompt, timeout=300)
        if reply is None:
            raise RuntimeError("Session became idle without an assistant message.")
        host.report_outcome()
        print(f"[agent commentary] {reply.data.content}")
    finally:
        unsubscribe()


async def main() -> None:
    host = ReviewHost()
    try:
        async with asyncio.timeout(360):
            async with CopilotClient() as client:
                options = {
                    "working_directory": str(REPO_ROOT),
                    "available_tools": ToolSet().add_builtin(["ask_user", SHELL_TOOL]),
                    "on_permission_request": host.on_permission_request,
                    "hooks": {"on_pre_tool_use": host.on_pre_tool_use},
                }
                async with await client.create_session(
                    **options,
                    ask_user_variant="elicitation",
                    on_elicitation_request=host.on_elicitation_request,
                ) as session:
                    if await has_structured_ask_user(session):
                        await run_conversation(session, host, structured=True)
                        return
                print(
                    "[hitl] Structured ask_user is unavailable in this runtime; "
                    "falling back to the legacy question contract."
                )
                async with await client.create_session(
                    **options,
                    ask_user_variant="legacy",
                    on_user_input_request=host.on_user_input_request,
                ) as session:
                    await run_conversation(session, host, structured=False)
    except asyncio.CancelledError:
        print("[host] COMMAND_CANCELLED; no result verified", file=sys.stderr)
        raise
    except Exception as exc:
        print(f"[host] COMMAND_INCOMPLETE reason={exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    asyncio.run(main())
