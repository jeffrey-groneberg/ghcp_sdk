"""
Example 08: a sandbox with one human-approved exception.

The runtime sandbox denies a disposable vault folder. grep is asked to search
it, the sandbox blocks the call, and because allow_bypass is on, the runtime
asks your code whether this one call may run outside the sandbox. Only your y
approves it. Example 13 shows the sandbox without any bypass. SandboxConfig and
its policy types are experimental in SDK 2.0.1.

Run: python examples/08_sandbox.py
"""

import asyncio
import tempfile
from pathlib import Path

from copilot import CopilotClient
from copilot.rpc import (PermissionDecisionApproveOnce, PermissionDecisionReject, SandboxConfig,
                         SandboxConfigUserPolicy, SandboxConfigUserPolicyFilesystem,
                         SandboxConfigUserPolicyNetwork)
from copilot.session_events import ToolExecutionCompleteData

MARKER = "OUTSIDE_MATCH_LINE sandbox-bypass-approved"


async def on_permission(request, invocation):
    if not getattr(request, "request_sandbox_bypass", False):
        return PermissionDecisionApproveOnce()  # runs inside the sandbox
    target = getattr(request, "path", None) or getattr(request, "full_command_text", "")
    answer = await asyncio.to_thread(
        input, f"\n[sandbox bypass] {target}\nRun this one call outside the sandbox? [y/N] ")
    if answer.strip().lower() == "y":
        return PermissionDecisionApproveOnce()
    return PermissionDecisionReject(feedback="The user rejected the sandbox bypass.")


def on_event(event):
    match event.data:
        case ToolExecutionCompleteData(success=ok, sandboxed=sandboxed, result=result):
            found = bool(result and MARKER in (result.content or ""))
            print(f"[tool] success={ok} sandboxed={sandboxed} marker found={found}")


async def main() -> None:
    with tempfile.TemporaryDirectory() as workspace:
        vault = Path(workspace, "vault")
        vault.mkdir()
        (vault / "notes.txt").write_text(MARKER + "\n")
        sandbox = SandboxConfig(
            enabled=True, add_current_working_directory=True,
            allow_bypass=True,  # the runtime may ask to run one call outside
            user_policy=SandboxConfigUserPolicy(
                filesystem=SandboxConfigUserPolicyFilesystem(denied_paths=[str(vault)]),
                network=SandboxConfigUserPolicyNetwork(allow_outbound=False,
                                                       allow_local_network=False)))
        async with CopilotClient(mode="coding-agent") as client:
            session = await client.create_session(
                working_directory=workspace,
                tools={"available_tools": ["builtin:grep"]},
                permissions={"on_request": on_permission, "sandbox": sandbox},
                events={"on_event": on_event})
            reply = await session.send_and_wait(
                f"Use grep once to search {vault} for the exact text {MARKER!r}. "
                "Report whether it was found. Use no other tool or path.", timeout=180)
            print(f"\n{reply.data.content if reply else 'no answer'}")


if __name__ == "__main__":
    asyncio.run(main())
