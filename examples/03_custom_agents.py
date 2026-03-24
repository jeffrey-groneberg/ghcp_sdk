"""
Example 3: Custom Agents — Define specialized AI personas.

Creates three agents with different roles (researcher, writer, reviewer)
and lets Copilot automatically pick the right one based on the question.

Prerequisites:
    pip install github-copilot-sdk
    Copilot CLI installed and signed in (or set COPILOT_GITHUB_TOKEN)

Usage:
    python 03_custom_agents.py
"""

import asyncio

from copilot import CopilotClient, PermissionHandler
from copilot.generated.session_events import SessionEventType


async def main():
    client = CopilotClient()
    await client.start()

    # Define three agents, each with a focused role and scoped tools
    session = await client.create_session(
        on_permission_request=PermissionHandler.approve_all,
        model="gpt-4.1",
        streaming=True,
        custom_agents=[
            {
                "name": "researcher",
                "display_name": "Research Agent",
                "description": "Explores codebases, reads files, and answers questions. Read-only.",
                "tools": ["grep", "glob", "view"],
                "prompt": (
                    "You are a research assistant. Your job is to analyze code, "
                    "find patterns, and answer questions thoroughly. "
                    "Never modify any files — read-only access only."
                ),
                "infer": True,  # Copilot can auto-select this agent
            },
            {
                "name": "writer",
                "display_name": "Code Writer",
                "description": "Writes and edits code files.",
                "tools": ["view", "edit", "bash"],
                "prompt": (
                    "You are a code writer. Write clean, well-commented code. "
                    "Follow existing code style and conventions in the project."
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
                    "Provide specific line references and suggested fixes."
                ),
                "infer": True,
            },
        ],
        agent="researcher",  # Start with the researcher selected
    )

    # Track which agent is active
    def on_event(event):
        if event.type == SessionEventType.ASSISTANT_MESSAGE_DELTA:
            print(event.data.delta_content, end="", flush=True)
        elif event.type == SessionEventType.SUBAGENT_STARTED:
            print(f"\n🤖 [Agent switched to: {event.data.agent_display_name}]")
        elif event.type == SessionEventType.SUBAGENT_COMPLETED:
            print(f"\n✅ [Agent finished: {event.data.agent_display_name}]")

    session.on(on_event)

    # The researcher agent handles this naturally
    prompt1 = "What files are in this project and what does the project do?"
    print(f"You: {prompt1}\n")
    print("Copilot: ", end="")
    await session.send_and_wait(prompt1, timeout=180)
    print("\n")

    # Copilot may auto-delegate to the reviewer agent
    prompt2 = "Review the code in this project for any security concerns."
    print(f"You: {prompt2}\n")
    print("Copilot: ", end="")
    await session.send_and_wait(prompt2, timeout=180)
    print("\n")

    await session.disconnect()
    await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
