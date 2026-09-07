"""
Example 04 — Hooks (GitHub Copilot SDK 1.0.13)

Hooks are callbacks that fire at well-defined points in the agent's
lifecycle (before/after a tool call, on submit, on stop, ...).

They are perfect for cross-cutting concerns that should not pollute
your tool implementations:
  * Audit logging                ("which tools did the agent use?")
  * Telemetry / metrics
  * Caching of expensive tools
  * Soft policy enforcement     (e.g. "warn if writing outside repo")

This example traces tool requests, successful results and failed results
while the agent lists the working directory.

Run:
    python examples/04_hooks.py
"""

import asyncio

from copilot import CopilotClient
from copilot.session import PermissionHandler


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
    print(f"[failed] {input_data['toolName']}")
    return None


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
            model="gpt-5-mini",
            # Only read/list tools in this trusted demonstration; no shell.
            available_tools=["builtin:glob", "builtin:view"],
            hooks={
                "on_pre_tool_use": on_pre_tool_use,
                "on_post_tool_use": on_post_tool_use,
                "on_post_tool_use_failure": on_post_tool_use_failure,
            },
        ) as session:
            # Request tool use, then inspect the trace: a prompt is not proof
            # that the model actually invoked a tool.
            reply = await session.send_and_wait(
                "Use glob or view to list the files in the current directory.",
                timeout=120,
            )
            if reply is None:
                raise RuntimeError("Session became idle without an assistant message.")
            print("\n", reply.data.content)


if __name__ == "__main__":
    asyncio.run(main())
