"""
Example 6: Human-in-the-Loop — Interactive approvals and user input.

Demonstrates two key patterns for keeping a human in control:

  1. Permission Requests (on_permission_request):
     The agent must ask before running shell commands, writing files, etc.
     Your handler decides: approve, deny, or deny with a reason.

  2. User Input Requests (on_user_input_request):
     The agent can ask the user questions via the ask_user tool.
     Your handler displays the question and returns the answer.

Together these let you build agents that collaborate with users
rather than running fully autonomously.

Prerequisites:
    pip install github-copilot-sdk
    Copilot CLI installed and signed in (or set COPILOT_GITHUB_TOKEN)

Usage:
    python 06_human_in_the_loop.py
"""

import asyncio
from copilot import CopilotClient, PermissionHandler
from copilot.types import PermissionRequest, PermissionRequestResult
from copilot.generated.session_events import SessionEventType


# ── Permission Handler ───────────────────────────────────────
# Called before every tool execution. You decide: approve or deny.
# This replaces PermissionHandler.approve_all with interactive control.

ALWAYS_ALLOW = {"read_file", "glob", "grep", "view", "list_dir", "web_fetch"}

def on_permission_request(
    request: PermissionRequest,
    invocation: dict,
) -> PermissionRequestResult:
    kind = request.kind.value  # "shell", "write", "read", "mcp", "custom-tool", "url", etc.

    # Auto-approve read-only operations
    if kind == "read":
        return PermissionRequestResult(kind="approved")

    # Build a human-readable description of what the agent wants to do
    description = f"  Type: {kind}"
    if hasattr(request, "tool_name") and request.tool_name:
        description += f"\n  Tool: {request.tool_name}"
    if hasattr(request, "full_command_text") and request.full_command_text:
        description += f"\n  Command: {request.full_command_text}"
    if hasattr(request, "file_name") and request.file_name:
        description += f"\n  File: {request.file_name}"

    # Ask the human
    print(f"\n🔐 Permission requested:\n{description}")
    choice = input("  Allow? [y/n]: ").strip().lower()

    if choice == "y":
        print("  ✅ Approved")
        return PermissionRequestResult(kind="approved")
    else:
        print("  🚫 Denied")
        return PermissionRequestResult(kind="denied-interactively-by-user")


# ── User Input Handler ───────────────────────────────────────
# Called when the agent uses the ask_user tool to ask a question.
# You display the question and return the user's answer.

async def on_user_input_request(request: dict, invocation: dict) -> dict:
    question = request.get("question", "")
    choices = request.get("choices", [])
    allow_freeform = request.get("allowFreeform", True)

    print(f"\n💬 Agent asks: {question}")

    if choices:
        print("  Options:")
        for i, choice in enumerate(choices, 1):
            print(f"    {i}. {choice}")

        if allow_freeform:
            print("    (or type a custom answer)")

        answer = input("  Your answer: ").strip()

        # If they typed a number, map to the choice
        if answer.isdigit() and 1 <= int(answer) <= len(choices):
            selected = choices[int(answer) - 1]
            print(f"  → Selected: {selected}")
            return {"answer": selected, "wasFreeform": False}

        return {"answer": answer, "wasFreeform": True}
    else:
        answer = input("  Your answer: ").strip()
        return {"answer": answer, "wasFreeform": True}


# ── Main ─────────────────────────────────────────────────────
async def main():
    client = CopilotClient()
    await client.start()

    session = await client.create_session(
        # Interactive permission handler instead of approve_all
        on_permission_request=on_permission_request,
        # Enable the ask_user tool so the agent can ask us questions
        on_user_input_request=on_user_input_request,
        model="gpt-4.1",
        streaming=True,
    )

    # Stream output
    def on_event(event):
        if event.type == SessionEventType.ASSISTANT_MESSAGE_DELTA:
            print(event.data.delta_content, end="", flush=True)

    session.on(on_event)

    # This prompt will likely trigger:
    #  - Permission requests (reading files, maybe running shell commands)
    #  - User input requests (clarifying questions about what to analyze)
    prompt = (
        "Look at the files in this directory. "
        "Ask me which file I'd like you to analyze, "
        "then give me a summary of what it does. "
        "If you think any improvements could be made, ask me if I want you to apply them."
    )

    print(f"You: {prompt}\n")
    print("Copilot: ", end="")
    await session.send_and_wait(prompt)
    print("\n")

    await session.disconnect()
    await client.stop()
    print("--- Session ended ---")


if __name__ == "__main__":
    asyncio.run(main())
