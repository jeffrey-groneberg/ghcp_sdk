"""
Example 3: Custom Agents — Define specialized AI personas.

Creates three agents with different roles (researcher, writer, reviewer)
and explicitly selects each one to demonstrate agent handoff.

Prerequisites:
    pip install github-copilot-sdk
    Copilot CLI installed and signed in (or set COPILOT_GITHUB_TOKEN)

Usage:
    python 03_custom_agents.py
"""

import asyncio

from copilot import CopilotClient, PermissionHandler
from copilot.generated.rpc import SessionAgentSelectParams
from copilot.generated.session_events import SessionEventType


async def main():
    client = CopilotClient()
    await client.start()

    # Define three agents, each with a focused role and scoped tools
    session_agents = [
        {
            "name": "researcher",
            "display_name": "Research Agent",
            "description": "Explores codebases, reads files, and answers questions. Read-only.",
            "tools": ["grep", "glob", "view"],
            "prompt": (
                "You are a research assistant. Your job is to analyze code, "
                "find patterns, and answer questions thoroughly. "
                "Never modify any files — read-only access only. "
                "Always respond inline with your findings."
            ),
            "infer": True,
        },
        {
            "name": "writer",
            "display_name": "Code Writer",
            "description": "Writes and edits code files.",
            "tools": ["view", "edit", "bash"],
            "prompt": (
                "You are a code writer. Write clean, well-commented code. "
                "Follow existing code style and conventions in the project. "
                "Always respond inline with your findings."
            ),
            "infer": True,
        },
        {
            "name": "reviewer",
            "display_name": "Code Reviewer",
            "description": "Reviews code for bugs, security issues, and best practices.",
            "tools": ["grep", "glob", "view"],
            "prompt": (
                "You are a senior code reviewer. Focus on:\n"
                "1. Security vulnerabilities (OWASP Top 10)\n"
                "2. Performance issues (N+1 queries, memory leaks)\n"
                "3. Error handling (missing try/catch, unhandled promises)\n"
                "4. Code clarity and maintainability\n"
                "Provide specific line references and suggested fixes. "
                "Always respond inline with your findings."
            ),
            "infer": True,
        },
    ]

    session = await client.create_session(
        on_permission_request=PermissionHandler.approve_all,
        model="gpt-4.1",
        streaming=True,
        custom_agents=session_agents,
        agent="researcher",  # Start with the researcher selected
    )

    # Track the active agent name for display
    active_agent = "Research Agent"

    def on_event(event):
        nonlocal active_agent
        if event.type == SessionEventType.ASSISTANT_MESSAGE_DELTA:
            print(event.data.delta_content, end="", flush=True)
        elif event.type == SessionEventType.SUBAGENT_STARTED:
            active_agent = event.data.agent_display_name
            print(f"\n🤖 [Agent started: {active_agent}]")
        elif event.type == SessionEventType.SUBAGENT_COMPLETED:
            print(f"\n✅ [Agent finished: {event.data.agent_display_name}]")
        elif event.type == SessionEventType.SUBAGENT_SELECTED:
            active_agent = event.data.agent_display_name
            print(f"\n🔀 [Agent selected: {active_agent}]")
        elif event.type == SessionEventType.SUBAGENT_FAILED:
            print(f"\n❌ [Agent failed: {event.data.agent_name}]")
        elif event.type == SessionEventType.SESSION_ERROR:
            msg = getattr(event.data, "message", str(event.data))
            print(f"\n⚠️  [Session error: {msg}]")

    session.on(on_event)

    # ── Step 1: Researcher explores the project ─────────────────
    print("=" * 60)
    print("STEP 1 — Research Agent: Explore the project")
    print("=" * 60)

    prompt1 = "What programming language is this project written in and what are its main dependencies?"
    print(f"\nYou: {prompt1}\n")
    print(f"🔹 [{active_agent}]: ", end="")
    await session.send_and_wait(prompt1, timeout=120)
    print("\n")

    # ── Step 2: Switch to reviewer ──────────────────────────────
    await session.rpc.agent.select(SessionAgentSelectParams(name="reviewer"))
    active_agent = "Code Reviewer"

    print("=" * 60)
    print("STEP 2 — Code Reviewer: Review error handling")
    print("=" * 60)

    prompt2 = "Review examples/01_simple_chat.py for error handling and robustness issues."
    print(f"\nYou: {prompt2}\n")
    print(f"🔹 [{active_agent}]: ", end="")
    await session.send_and_wait(prompt2, timeout=120)
    print("\n")

    # ── Step 3: Switch to writer ────────────────────────────────
    await session.rpc.agent.select(SessionAgentSelectParams(name="writer"))
    active_agent = "Code Writer"

    print("=" * 60)
    print("STEP 3 — Code Writer: Improve the code")
    print("=" * 60)

    prompt3 = (
        "Based on the review above, show me an improved version of the main() "
        "call in examples/01_simple_chat.py that wraps it with proper error handling "
        "using try/except. Just print the code, don't create any files."
    )
    print(f"\nYou: {prompt3}\n")
    print(f"🔹 [{active_agent}]: ", end="")
    await session.send_and_wait(prompt3, timeout=120)
    print("\n")

    await session.disconnect()
    await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
