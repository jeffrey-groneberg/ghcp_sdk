"""
Example 12: approval in code, only the exact match is approved (deck slide 32).

A pre-tool hook sees every tool call first and denies anything on a block list.
Then on_permission approves one exact command and rejects everything else. Run
1 shows the hook stopping rm -rf. Run 2 asks for rm -r -f, which the block list
misses, and the exact match still rejects it. It uses the bash tool, so it needs
macOS or Linux. PermissionDecisionApproveOnce and PermissionDecisionReject are
experimental in SDK 2.0.1.

Run: python examples/12_approval.py
"""

import asyncio

from copilot import CopilotClient, ToolSet
from copilot.rpc import PermissionDecisionApproveOnce, PermissionDecisionReject

from _demo_repo import make_demo_repo


async def pre_tool_use(hook_input, invocation):
    command = (hook_input["toolArgs"] or {}).get("command", "")
    if any(p in str(hook_input["toolArgs"]) for p in ("rm -rf", "sudo")):
        print(f"[hook] denied: {command}")
        return {"permissionDecision": "deny",
                "permissionDecisionReason": "Blocked by policy"}
    print(f"[hook] passed: {command}")


def on_permission(request, invocation):
    command = getattr(request, "full_command_text", "")
    if command == "git status":
        print(f"[approval] approved: {command}")
        return PermissionDecisionApproveOnce()
    print(f"[approval] rejected: {command}")
    return PermissionDecisionReject(feedback="Not approved in this demo.")


PROMPTS = [
    "First run `git status` as its own command. Then, as a separate command, run "
    "`rm -rf build`. Do not combine them. Report briefly what happened.",
    "Run exactly `rm -r -f build` once. Do not retry or rephrase. Report what happened.",
]


async def main() -> None:
    repo = make_demo_repo()
    (repo / "build").mkdir()
    (repo / "build" / "artifact.o").write_text("demo")
    async with CopilotClient(mode="coding-agent") as client:
        for run, prompt in enumerate(PROMPTS, start=1):
            print(f"--- run {run}")
            session = await client.create_session(
                working_directory=str(repo),
                tools={"available_tools": ToolSet().add_builtin("bash")},
                hooks={"handlers": {"on_pre_tool_use": pre_tool_use}},
                permissions={"on_request": on_permission})
            reply = await session.send_and_wait(prompt, timeout=180)
            print(f"agent: {reply.data.content if reply else 'no answer'}")
            print(f"build/ still there: {(repo / 'build').exists()}")


if __name__ == "__main__":
    asyncio.run(main())
