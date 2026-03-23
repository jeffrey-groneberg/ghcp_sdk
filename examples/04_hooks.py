"""
Example 4: Hooks — Intercept and control session behavior.

Demonstrates all major hook types:
  - onSessionStart   → log + inject context
  - onPreToolUse     → enforce an allow-list of tools
  - onPostToolUse    → redact secrets from tool output
  - onUserPromptSubmitted → expand shorthand commands
  - onErrorOccurred  → auto-retry on transient errors
  - onSessionEnd     → print a session summary

Prerequisites:
    pip install github-copilot-sdk
    Copilot CLI installed and signed in (or set COPILOT_GITHUB_TOKEN)

Usage:
    python 04_hooks.py
"""

import asyncio
import re
import time

from copilot import CopilotClient, PermissionHandler
from copilot.generated.session_events import SessionEventType

# ── Session metrics (populated by hooks) ─────────────────────────
session_stats = {"prompts": 0, "tools_allowed": 0, "tools_denied": 0, "secrets_redacted": 0, "start": 0}

ALLOWED_TOOLS = ["read_file", "glob", "grep", "view", "get_weather"]


# ── Hook: Session Start ─────────────────────────────────────────
async def on_session_start(input_data, invocation):
    session_stats["start"] = time.time()
    print(f"📋 [Hook] Session started (id: {invocation['sessionId'][:12]}...)")
    return {"additionalContext": "This is a Python project. Follow PEP 8 style guidelines."}


# ── Hook: Pre-Tool Use (access control) ─────────────────────────
async def on_pre_tool_use(input_data, invocation):
    tool = input_data["toolName"]
    if tool not in ALLOWED_TOOLS:
        session_stats["tools_denied"] += 1
        print(f"🚫 [Hook] DENIED tool: {tool}")
        return {
            "permissionDecision": "deny",
            "permissionDecisionReason": f'Tool "{tool}" is not in the allowed list.',
        }
    session_stats["tools_allowed"] += 1
    print(f"✅ [Hook] Allowed tool: {tool}")
    return {"permissionDecision": "allow"}


# ── Hook: Post-Tool Use (secret redaction) ───────────────────────
async def on_post_tool_use(input_data, invocation):
    result = input_data.get("toolResult", "")
    if isinstance(result, str):
        redacted = re.sub(
            r"(api[_-]?key|secret|password|token)\s*[:=]\s*[\"']?[\w\-\.]+[\"']?",
            r"\1=[REDACTED]",
            result,
            flags=re.IGNORECASE,
        )
        if redacted != result:
            session_stats["secrets_redacted"] += 1
            print("🔒 [Hook] Redacted secrets from tool output")
            return {"modifiedResult": redacted}
    return None


# ── Hook: User Prompt (shorthand expansion) ──────────────────────
async def on_user_prompt_submitted(input_data, invocation):
    prompt = input_data["prompt"]
    session_stats["prompts"] += 1

    # Expand shorthand commands into full instructions
    shortcuts = {
        "/review": "Review the current file for bugs, security issues, and code quality.",
        "/explain": "Explain what this code does in simple terms.",
        "/test": "Write unit tests for the functions in the current file.",
    }
    for shortcut, expansion in shortcuts.items():
        if prompt.strip().startswith(shortcut):
            print(f"🔄 [Hook] Expanded '{shortcut}' → full instruction")
            return {"modifiedPrompt": expansion}

    return None


# ── Hook: Error Handling ─────────────────────────────────────────
async def on_error_occurred(input_data, invocation):
    context = input_data.get("errorContext", "unknown")
    recoverable = input_data.get("recoverable", False)
    print(f"⚠️  [Hook] Error in {context} (recoverable: {recoverable})")
    if recoverable:
        return {"errorHandling": "retry", "retryCount": 2}
    return None


# ── Hook: Session End ────────────────────────────────────────────
async def on_session_end(input_data, invocation):
    duration = round(time.time() - session_stats["start"], 1)
    print(f"""
📊 [Hook] Session Summary
   Duration:        {duration}s
   Prompts sent:    {session_stats["prompts"]}
   Tools allowed:   {session_stats["tools_allowed"]}
   Tools denied:    {session_stats["tools_denied"]}
   Secrets redacted:{session_stats["secrets_redacted"]}
   End reason:      {input_data.get("reason", "unknown")}
""")
    return None


# ── Main ─────────────────────────────────────────────────────────
async def main():
    client = CopilotClient()
    await client.start()

    session = await client.create_session(
        {
            "on_permission_request": PermissionHandler.approve_all,
            "model": "gpt-4.1",
            "streaming": True,
            "hooks": {
                "on_session_start": on_session_start,
                "on_pre_tool_use": on_pre_tool_use,
                "on_post_tool_use": on_post_tool_use,
                "on_user_prompt_submitted": on_user_prompt_submitted,
                "on_error_occurred": on_error_occurred,
                "on_session_end": on_session_end,
            },
        }
    )

    def on_event(event):
        if event.type == SessionEventType.ASSISTANT_MESSAGE_DELTA:
            print(event.data.delta_content, end="", flush=True)

    session.on(on_event)

    # Regular prompt
    print("\nYou: What files are in this directory?\n")
    print("Copilot: ", end="")
    await session.send_and_wait("What files are in this directory?")
    print("\n")

    # Shorthand prompt — the hook will expand "/explain" automatically
    print("You: /explain\n")
    print("Copilot: ", end="")
    await session.send_and_wait("/explain")
    print("\n")

    await session.disconnect()
    await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
