"""
Example 04 — Hooks

Hooks are callbacks that fire at well-defined points in the agent's
lifecycle (before/after a tool call, on submit, on stop, ...).

They are perfect for cross-cutting concerns that should not pollute
your tool implementations:
  * Audit logging                ("which tools did the agent use?")
  * Telemetry / metrics
  * Caching of expensive tools
  * Soft policy enforcement     (e.g. "warn if writing outside repo")

This example wires up the two most common hooks and prints a trace of
every tool call the agent makes while listing the working directory.

Run:
    python examples/04_hooks.py
"""

import asyncio

from copilot import CopilotClient
from copilot.session import PermissionHandler


# `on_pre_tool_use` fires *just before* the agent invokes a tool.
#
# Signature:
#   input_data: dict — { "toolName": str, "toolInput": dict, ... }
#   invocation: dict — { "session_id": str }
#
# Return value semantics:
#   * `None`                                → no opinion, let the tool run
#   * { "permissionDecision": "allow" }     → allow (skip the permission prompt)
#   * { "permissionDecision": "deny",
#       "permissionDecisionReason": "..." } → cancel the tool call; the agent
#                                             sees the reason and can adapt
#   * { "permissionDecision": "ask" }       → defer to the permission handler
#   * { "modifiedArgs": {...} }             → rewrite the tool's arguments
async def on_pre_tool_use(input_data, invocation):
    print(f"[pre]  {input_data['toolName']}")
    return None


# `on_post_tool_use` fires *after* the tool returns (success or failure).
# Great spot for logging duration, persisting results, etc.
# Same signature; returning `None` means "no opinion".
async def on_post_tool_use(input_data, invocation):
    print(f"[post] {input_data['toolName']} done")
    return None


async def main() -> None:
    async with CopilotClient() as client:
        # Hooks are registered as a plain dict keyed by hook name. The
        # SDK supports several others — `on_user_prompt_submit`,
        # `on_stop`, `on_session_start`, ... — but the two below cover
        # 90% of real-world use cases.
        async with await client.create_session(
            on_permission_request=PermissionHandler.approve_all,
            model="gpt-4.1",
            hooks={
                "on_pre_tool_use": on_pre_tool_use,
                "on_post_tool_use": on_post_tool_use,
            },
        ) as session:
            # The "list files" prompt is chosen because it forces the agent
            # to use at least one built-in tool (usually `glob` or `view`),
            # so we can see both hooks fire in the output.
            reply = await session.send_and_wait(
                "List the files in the current directory.",
                timeout=120,
            )
            if reply:
                print("\n", reply.data.content)


if __name__ == "__main__":
    asyncio.run(main())
