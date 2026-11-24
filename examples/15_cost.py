"""
Example 15: cap and watch cost.

execution.limits.max_ai_credits sets a soft AI-credit cap for the session
(checked after each model call). Every model call emits an assistant.usage
event, and session.rpc.usage.get_metrics() returns the session's totals.
max_ai_credits, the usage event's cost field and the UsageApi group
(session.rpc.usage) are experimental in SDK 2.0.1. The SDK docs convert nano
AI units to AI credits by dividing by 1e9; GitHub billing is authoritative.

Run: python examples/15_cost.py
"""

import asyncio

from copilot import CopilotClient
from copilot.session_events import AssistantUsageData


def on_event(event):
    match event.data:
        case AssistantUsageData() as usage:
            credits = usage.copilot_usage.total_nano_aiu / 1e9 if usage.copilot_usage else None
            print(f"[assistant.usage] {usage.model}: {usage.input_tokens} tokens in, "
                  f"{usage.output_tokens} out, AI credits: {credits}")


async def main() -> None:
    async with CopilotClient(mode="coding-agent") as client:
        session = await client.create_session(
            tools={"available_tools": []},
            execution={"limits": {"max_ai_credits": 5}},  # soft cap for this session
            events={"on_event": on_event})
        reply = await session.send_and_wait(
            "In one sentence: why cap an agent's spending?", timeout=60)
        print(reply.data.content if reply else "no answer")
        metrics = await session.rpc.usage.get_metrics()
        print(f"session total: {(metrics.total_nano_aiu or 0) / 1e9:.4f} AI credits "
              f"({getattr(metrics.ai_credits_status, 'value', 'unknown')}), "
              f"premium request cost: {metrics.total_premium_request_cost}")


if __name__ == "__main__":
    asyncio.run(main())
