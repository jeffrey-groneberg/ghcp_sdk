"""
Example 08 — Deny or approve access to one disposable private review note.

Run from the repository root: python examples/08_sandbox.py
Source: https://github.com/github/copilot-sdk/blob/v1.0.13/nodejs/test/e2e/sandbox_bypass.e2e.test.ts

Experimental runtime sandbox, not isolation of host Python callbacks. No real
secrets are used. Approval alone, filenames, and generic success are not proof.
"""

import asyncio
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile

from copilot import CopilotClient, PermissionRequestResult, ToolSet
from copilot.rpc import (
    PermissionDecisionApproveOnce,
    PermissionDecisionReject,
    PermissionDecisionUserNotAvailable,
    SandboxConfig,
    SandboxConfigUserPolicy,
    SandboxConfigUserPolicyFilesystem,
    SandboxConfigUserPolicyNetwork,
    SessionUpdateOptionsParams,
)
from copilot.session_events import (
    PermissionRequestRead,
    ToolExecutionCompleteData,
    ToolExecutionStartData,
)

from _console_input import read_answer
from _tool_trace import ToolTrace


REPO_ROOT = Path(__file__).resolve().parents[1]
REVIEW_FILE = "examples/01_simple_chat.py"
INPUT_TIMEOUT = 120
NOTE_FILENAME = "review-note.txt"
NOTE_PREFIX = "WORKSHOP_PRIVATE_REVIEW_NOTE"
SEARCH_PATTERN = "^" + NOTE_PREFIX + " "


def make_review_note() -> str:
    return (
        f"{NOTE_PREFIX} file={REVIEW_FILE}; focus=error handling; "
        "check final-message handling and listener cleanup; nonce=" + secrets.token_hex(16)
    )


@dataclass
class ApprovalState:
    vault: Path
    note_content: str
    trace: ToolTrace = field(default_factory=ToolTrace)
    hook_accepted: bool = False
    bypass_requested: bool = False
    bypass_call_id: str | None = None
    bypass_decision: str | None = None

    @property
    def grep_arguments(self) -> dict:
        return {
            "pattern": SEARCH_PATTERN,
            "paths": str(self.vault),
            "glob": NOTE_FILENAME,
            "output_mode": "content",
            "-n": True,
            "head_limit": 1,
        }


def sandbox_runtime_env() -> dict[str, str]:
    env = os.environ.copy()
    flags = {
        flag.strip()
        for flag in env.get("COPILOT_CLI_ENABLED_FEATURE_FLAGS", "").split(",")
        if flag.strip()
    }
    flags.add("SANDBOX")
    env["COPILOT_CLI_ENABLED_FEATURE_FLAGS"] = ",".join(sorted(flags))
    return env


async def require_content_grep(session) -> None:
    """Inspect capabilities, without assuming a successful search returns lines."""
    await session.rpc.tools.initialize_and_validate()
    metadata = await session.rpc.tools.get_current_metadata()
    for tool in metadata.tools or []:
        if tool.name == "grep" and isinstance(tool.input_schema, dict):
            properties = tool.input_schema.get("properties")
            if isinstance(properties, dict):
                output = properties.get("output_mode")
                if (
                    isinstance(output, dict)
                    and "content" in output.get("enum", [])
                    and {"pattern", "paths", "glob", "-n", "head_limit"} <= set(properties)
                ):
                    print("[sandbox] grep content-output metadata confirmed")
                    return
    raise RuntimeError("Runtime grep metadata does not expose the required scoped content output.")


def scoped_grep_hook(state: ApprovalState):
    async def on_pre_tool_use(input_data, invocation):
        if (
            input_data["toolName"] != "grep"
            or input_data.get("workingDirectory") != str(state.vault.parent)
            or input_data.get("toolArgs") != state.grep_arguments
            or state.hook_accepted
        ):
            print("[sandbox hook] denied: only one exact scoped content grep is allowed.")
            return {
                "permissionDecision": "deny",
                "permissionDecisionReason": "Use only the one exact scoped content grep request.",
            }
        state.hook_accepted = True
        # This hook has no tool-call ID in 1.0.13; it is NOT the approval record.
        return None
    return on_pre_tool_use


def permission_handler(state: ApprovalState):
    async def on_permission_request(request, invocation) -> PermissionRequestResult:
        call_id = getattr(request, "tool_call_id", None)
        in_scope = False
        if isinstance(request, PermissionRequestRead):
            try:
                path = Path(request.path)
                in_scope = path.is_absolute() and path.resolve(strict=True) in {
                    state.vault, state.vault / NOTE_FILENAME,
                }
            except (OSError, RuntimeError, ValueError):
                pass
        if not in_scope or not call_id:
            print(f"[host] SANDBOX_BYPASS_DENIED id={call_id or 'missing'} reason=outside the scoped read policy")
            return PermissionDecisionReject(feedback="Only the correlated disposable-vault read is allowed.")

        if request.request_sandbox_bypass is not True:
            if request.managed_approval_required is True:
                print(f"[host] SANDBOX_BYPASS_DENIED id={call_id} reason=managed read approval unavailable")
                return PermissionDecisionUserNotAvailable()
            print(f"[host] SANDBOX_SCOPED_READ_APPROVE_ONCE id={call_id}; bypass=False")
            return PermissionDecisionApproveOnce()

        if state.bypass_requested:
            print(f"[host] SANDBOX_BYPASS_DENIED id={call_id} reason=only one bypass decision is allowed")
            return PermissionDecisionReject(feedback="Only one sandbox-bypass decision is allowed.")
        state.bypass_requested = True
        state.bypass_call_id = request.tool_call_id
        print(f"[sandbox bypass] {request.request_sandbox_bypass_reason or 'No reason supplied.'}")
        print(f"Target: {request.path}\nTool call ID: {call_id}")
        try:
            answer = await read_answer("Run this one grep outside the sandbox? [y/N]: ", timeout=INPUT_TIMEOUT)
        except (EOFError, OSError, TimeoutError):
            state.bypass_decision = "unavailable"
            print(f"[host] SANDBOX_BYPASS_DENIED id={call_id} reason=input unavailable or timed out")
            return PermissionDecisionUserNotAvailable()
        if answer.lower() == "y":
            state.bypass_decision = "approve-once"
            print(f"[host] SANDBOX_BYPASS_APPROVE_ONCE id={call_id}")
            return PermissionDecisionApproveOnce()
        state.bypass_decision = "reject"
        print(f"[host] SANDBOX_BYPASS_DENIED id={call_id} reason=user rejected")
        return PermissionDecisionReject(feedback="User rejected the sandbox bypass.")
    return on_permission_request


def record_grep_evidence(data: object, state: ApprovalState) -> str | None:
    state.trace.record(data)
    match data:
        case ToolExecutionStartData(tool_name="grep", tool_call_id=call_id, arguments=arguments):
            return f"[tool] grep started id={call_id} scoped={arguments == state.grep_arguments}"
        case ToolExecutionCompleteData(tool_call_id=call_id, success=success, sandboxed=sandboxed):
            start = state.trace.started.get(call_id)
            if start is not None and start.tool_name == "grep":
                return f"[tool] completed id={call_id} success={success} sandboxed={sandboxed}"
    return None


def bypass_verified(state: ApprovalState) -> bool:
    """The nonce is in the file and host memory, never in the model's prompt."""
    call_id = state.bypass_call_id
    start = state.trace.started.get(call_id)
    content = state.trace.successful_content(call_id)
    return bool(
        state.hook_accepted and state.bypass_requested
        and state.bypass_decision == "approve-once"
        and start is not None and start.tool_name == "grep"
        and start.arguments == state.grep_arguments
        and state.note_content and content is not None and state.note_content in content
    )


def report_outcome(state: ApprovalState) -> None:
    call_id = state.bypass_call_id
    for result_id, completion in state.trace.completed.items():
        if completion.result is not None and state.note_content in completion.result.content:
            if result_id != call_id or not bypass_verified(state):
                raise RuntimeError("Private note content arrived without matching scoped bypass approval and success.")
    if not state.bypass_requested or state.bypass_decision is None:
        raise RuntimeError("No host sandbox-bypass decision; tool/backend support is incomplete.")
    start = state.trace.started.get(call_id)
    completion = state.trace.completed.get(call_id)
    if (
        start is None or start.tool_name != "grep"
        or start.arguments != state.grep_arguments or completion is None
    ):
        raise RuntimeError("Missing matching scoped grep start/completion evidence.")
    if state.bypass_decision != "approve-once":
        if completion.success:
            raise RuntimeError("The denied grep reported success; access is unverified.")
        print(f"[host] SANDBOX_DENIAL_RECORDED id={call_id}; no access claimed")
        return
    if not bypass_verified(state):
        raise RuntimeError("Approved grep lacks a matching successful result containing the private note.")
    print(f"[host] SANDBOX_BYPASS_VERIFIED id={call_id}; matching result contains the private note")


async def main() -> None:
    try:
        if Path.cwd().resolve() != REPO_ROOT:
            raise RuntimeError("Run this example from the repository root.")
        # Explicit local directory: no system temporary directory or real secrets.
        with tempfile.TemporaryDirectory(prefix="copilot-sdk-review-", dir="examples") as directory:
            vault = Path(directory) / "vault"
            vault.mkdir(mode=0o700)
            note = make_review_note()
            (vault / NOTE_FILENAME).write_text(note + "\n", encoding="utf-8")
            state = ApprovalState(vault=vault.resolve(), note_content=note)
            async with asyncio.timeout(300):
                async with CopilotClient(env=sandbox_runtime_env()) as client:
                    async with await client.create_session(
                        on_permission_request=permission_handler(state),
                        working_directory=str(state.vault.parent),
                        available_tools=ToolSet().add_builtin("grep"),
                        hooks={"on_pre_tool_use": scoped_grep_hook(state)},
                    ) as session:
                        await require_content_grep(session)
                        updated = await session.rpc.options.update(
                            SessionUpdateOptionsParams(
                                sandbox_config=SandboxConfig(
                                    enabled=True,
                                    allow_bypass=True,  # Permission to ASK, never automatic approval.
                                    add_current_working_directory=True,
                                    user_policy=SandboxConfigUserPolicy(
                                        filesystem=SandboxConfigUserPolicyFilesystem(
                                            denied_paths=[str(state.vault)],
                                        ),
                                        network=SandboxConfigUserPolicyNetwork(
                                            allow_local_network=False,
                                            allow_outbound=False,
                                        ),
                                    ),
                                ),
                            )
                        )
                        if not updated.success:
                            raise RuntimeError("The runtime rejected the sandbox configuration.")

                        def on_event(event) -> None:
                            evidence = record_grep_evidence(event.data, state)
                            if evidence is not None:
                                print(evidence)
                            if isinstance(event.data, ToolExecutionCompleteData) and event.data.error:
                                print(f"[tool] failed: {event.data.error.message}", file=sys.stderr)

                        unsubscribe = session.on(on_event)
                        try:
                            reply = await session.send_and_wait(
                                f"A disposable private review note concerns {REVIEW_FILE}. "
                                "Use grep exactly once with these exact arguments:\n"
                                f"{json.dumps(state.grep_arguments)}\n"
                                "The vault is deliberately denied by the sandbox. "
                                "Only the host may approve one runtime-requested bypass. "
                                "Do not use other paths/tools or retry after a denial. "
                                "Describe the actual search result, not the host decision; "
                                "the host verifies approvals and note content independently.",
                                timeout=180,
                            )
                            if reply is None:
                                raise RuntimeError("Session became idle without an assistant message.")
                            report_outcome(state)
                        finally:
                            unsubscribe()
    except asyncio.CancelledError:
        print("[host] SANDBOX_CANCELLED; no access verified", file=sys.stderr)
        raise
    except Exception as exc:
        print(f"[host] SANDBOX_INCOMPLETE reason={exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    asyncio.run(main())
