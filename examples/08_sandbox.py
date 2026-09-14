"""
Example 08 — Experimental sandbox with a human-approved one-time bypass.

Run: python examples/08_sandbox.py
Source: https://github.com/github/copilot-sdk/blob/v1.0.13/nodejs/test/e2e/sandbox_bypass.e2e.test.ts

The sample creates only disposable marker data. A sandbox bypass executes the
approved tool call outside the sandbox, so production UIs must show the exact
request and default to denial.
"""

import asyncio
from dataclasses import dataclass
import os
from pathlib import Path
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


INPUT_TIMEOUT = 120
MARKER = "OUTSIDE_MATCH_LINE sandbox-bypass-approved"


@dataclass
class ApprovalState:
    bypass_requested: bool = False
    bypass_approved: bool = False
    grep_tool_call_id: str | None = None
    marker_found: bool = False


def sandbox_runtime_env() -> dict[str, str]:
    """Preserve the normal runtime environment and opt into the sandbox flag."""
    env = os.environ.copy()
    flags = {
        flag.strip()
        for flag in env.get("COPILOT_CLI_ENABLED_FEATURE_FLAGS", "").split(",")
        if flag.strip()
    }
    flags.add("SANDBOX")
    env["COPILOT_CLI_ENABLED_FEATURE_FLAGS"] = ",".join(sorted(flags))
    return env


def permission_handler(vault: Path, state: ApprovalState):
    vault = vault.resolve()

    async def on_permission_request(request, invocation) -> PermissionRequestResult:
        match request:
            case PermissionRequestRead(path=path):
                try:
                    requested_path = Path(path).resolve()
                    in_demo_vault = requested_path == vault or requested_path.is_relative_to(vault)
                except (OSError, RuntimeError):
                    in_demo_vault = False
                if not in_demo_vault:
                    return PermissionDecisionReject(
                        feedback="Only the disposable demo vault may be read."
                    )
            case _:
                return PermissionDecisionReject(
                    feedback="Only the scoped grep read is allowed in this example."
                )

        if request.request_sandbox_bypass is not True:
            if request.managed_approval_required is True:
                return PermissionDecisionUserNotAvailable()
            return PermissionDecisionApproveOnce()

        if state.bypass_requested:
            return PermissionDecisionReject(
                feedback="Only one sandbox-bypass decision is allowed."
            )
        state.bypass_requested = True
        reason = request.request_sandbox_bypass_reason or "No reason supplied."
        print(f"\n[sandbox bypass] {reason}\nTarget: {request.path}")
        try:
            answer = await read_answer(
                "Run this one grep outside the sandbox? [y/N]: ",
                timeout=INPUT_TIMEOUT,
            )
        except (EOFError, OSError, TimeoutError):
            return PermissionDecisionUserNotAvailable()
        if answer.lower() == "y":
            state.bypass_approved = True
            return PermissionDecisionApproveOnce()
        return PermissionDecisionReject(feedback="User rejected the sandbox bypass.")

    return on_permission_request


def record_grep_evidence(data: object, state: ApprovalState) -> str | None:
    """Track the denied marker from the tool result, not model phrasing."""
    match data:
        case ToolExecutionStartData(tool_name="grep", tool_call_id=tool_call_id):
            state.grep_tool_call_id = tool_call_id
            return "[tool] grep started"
        case ToolExecutionCompleteData(
            tool_call_id=tool_call_id,
            success=success,
            sandboxed=sandboxed,
            result=result,
        ) if tool_call_id == state.grep_tool_call_id:
            state.marker_found = bool(
                success and result is not None and MARKER in result.content
            )
            return f"[tool] completed success={success} sandboxed={sandboxed}"
    return None


async def main() -> None:
    state = ApprovalState()
    with tempfile.TemporaryDirectory(prefix="copilot-sdk-sandbox-") as temp_dir:
        workspace = Path(temp_dir)
        vault = workspace / "vault"
        vault.mkdir()
        (vault / "notes.txt").write_text(f"{MARKER}\n", encoding="utf-8")

        async with asyncio.timeout(300):
            async with CopilotClient(env=sandbox_runtime_env()) as client:
                async with await client.create_session(
                    on_permission_request=permission_handler(vault, state),
                    working_directory=str(workspace),
                    available_tools=ToolSet().add_builtin("grep"),
                ) as session:
                    updated = await session.rpc.options.update(
                        SessionUpdateOptionsParams(
                            sandbox_config=SandboxConfig(
                                enabled=True,
                                allow_bypass=True,
                                add_current_working_directory=True,
                                user_policy=SandboxConfigUserPolicy(
                                    filesystem=SandboxConfigUserPolicyFilesystem(
                                        denied_paths=[str(vault)],
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

                    unsubscribe = session.on(on_event)
                    try:
                        reply = await session.send_and_wait(
                            f"Use grep to search for the exact marker {MARKER!r} in "
                            f"{vault}. The directory is deliberately denied by the "
                            "sandbox. After the tool finishes, report whether the exact "
                            "marker was found. Do not claim whether the host approved a "
                            "sandbox bypass; the host verifies that independently. Use no "
                            "other tool or path.",
                            timeout=180,
                        )
                        if reply is None:
                            raise RuntimeError(
                                "Session became idle without an assistant message."
                            )
                        if state.marker_found and not state.bypass_approved:
                            raise RuntimeError(
                                "The denied marker was returned without a recorded host "
                                "sandbox-bypass approval."
                            )
                        if state.bypass_approved and not state.marker_found:
                            raise RuntimeError(
                                "The approved sandbox bypass completed without returning "
                                "the denied marker."
                            )
                        if state.marker_found:
                            print(
                                "\n[host] SANDBOX_BYPASS_APPROVED — explicit approval "
                                "and denied marker verified"
                            )
                        print(f"\n[agent] {reply.data.content}")
                    finally:
                        unsubscribe()


if __name__ == "__main__":
    asyncio.run(main())
