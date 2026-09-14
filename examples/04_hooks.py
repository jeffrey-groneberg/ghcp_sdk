"""
Example 04 — Hooks (GitHub Copilot SDK 1.0.13)

Hooks are callbacks that fire at well-defined points in the agent's
lifecycle (before/after a tool call, on submit, on stop, ...).

They are perfect for cross-cutting concerns that should not pollute
your tool implementations:
  * Audit logging                ("which tools did the agent use?")
  * Telemetry / metrics
  * Diagnostics

This example traces tool requests, successful results and failed results
while the agent reads the workshop's first Python sample. These hooks only
log; they do not enforce policy. Matching runtime events provide read evidence.

Run:
    python examples/04_hooks.py
"""

import asyncio
from pathlib import Path
import sys

from copilot import CopilotClient, ToolSet
from copilot.session import PermissionHandler

from _tool_trace import ToolTrace


REPO_ROOT = Path(__file__).resolve().parents[1]
REVIEW_FILE = "examples/01_simple_chat.py"
REVIEW_PATH = REPO_ROOT / REVIEW_FILE


# `on_pre_tool_use` fires *just before* the agent invokes a tool.
#
# Signature:
#   input_data: dict — { "toolName": str, "toolArgs": Any, ... }
#   invocation: dict — { "session_id": str }
#
# Return value semantics:
#   * `None`                                → no opinion; normal policy still applies
#   * { "permissionDecision": "allow" }     → request approval (not a policy bypass)
#   * { "permissionDecision": "deny",
#       "permissionDecisionReason": "..." } → cancel the tool call; the agent
#                                             sees the reason and can adapt
#   * { "permissionDecision": "ask" }       → defer to the permission handler
#   * { "modifiedArgs": {...} }             → rewrite the tool's arguments
async def on_pre_tool_use(input_data, invocation):
    print(f"[pre]  {input_data['toolName']}")
    return None


# `on_post_tool_use` runs after successful tool execution only.
# Failed tool results use `on_post_tool_use_failure` instead.
# Great spot for logging duration, persisting results, etc.
# Same signature; returning `None` means "no opinion".
async def on_post_tool_use(input_data, invocation):
    print(f"[post] {input_data['toolName']} succeeded")
    return None


async def on_post_tool_use_failure(input_data, invocation):
    print(
        f"[failed] {input_data['toolName']}: {input_data.get('error', 'unknown failure')}",
        file=sys.stderr,
    )
    return None


def is_review_read(start) -> bool:
    return (
        start.tool_name == "view"
        and isinstance(start.arguments, dict)
        and start.arguments.get("path") == str(REVIEW_PATH)
    )


async def main() -> None:
    async with asyncio.timeout(180):
        await run_conversation()


async def run_conversation() -> None:
    async with CopilotClient() as client:
        # Hooks are registered as a plain dict keyed by hook name. The
        # SDK supports several others — `on_user_prompt_submitted`,
        # `on_session_start`, `on_session_end`, `on_agent_stop`, ... .
        async with await client.create_session(
            on_permission_request=PermissionHandler.approve_all,
            working_directory=str(REPO_ROOT),
            available_tools=ToolSet().add_builtin("view"),
            hooks={
                "on_pre_tool_use": on_pre_tool_use,
                "on_post_tool_use": on_post_tool_use,
                "on_post_tool_use_failure": on_post_tool_use_failure,
            },
        ) as session:
            trace = ToolTrace()
            unsubscribe = session.on(lambda event: trace.record(event.data))
            try:
                reply = await session.send_and_wait(
                    f"Use view with the exact absolute path {str(REVIEW_PATH)!r}. "
                    "Explain how this sample handles errors and releases its "
                    "event subscription. Cite lines; do not modify anything.",
                    timeout=120,
                )
                if reply is None:
                    raise RuntimeError("Session became idle without an assistant message.")
                if not any(
                    is_review_read(start) and trace.successful_content(call_id)
                    for call_id, start in trace.started.items()
                ):
                    raise RuntimeError("No matching successful view result for the review file.")
                print(f"[host] READ_VERIFIED file={REVIEW_FILE}")
                print("\n", reply.data.content)
            finally:
                unsubscribe()


if __name__ == "__main__":
    asyncio.run(main())
