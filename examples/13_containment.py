"""
Example 13: containment, approved and still blocked (deck slide 33).

The permission handler approves every request, so only the sandbox can stop a
command. The policy denies a disposable vault folder and all network access,
with no bypass. Add --no-sandbox for the control run, which reads the vault and
reaches the network. The host, not the model, reports whether the secret reached
the agent. It uses the bash tool, so it needs macOS or Linux. SandboxConfig and
its policy types are experimental in SDK 2.0.1.

Run:
    python examples/13_containment.py
    python examples/13_containment.py --no-sandbox
"""

import asyncio
import sys
import tempfile
from pathlib import Path

from copilot import CopilotClient
from copilot.rpc import (SandboxConfig, SandboxConfigUserPolicy,
                         SandboxConfigUserPolicyFilesystem, SandboxConfigUserPolicyNetwork)
from copilot.session import PermissionHandler
from copilot.session_events import ToolExecutionCompleteData, ToolExecutionStartData


SECRET = "TOP-SECRET-MARKER"
outputs: list[str] = []  # every tool result the agent received


def on_event(event):
    match event.data:
        case ToolExecutionStartData(arguments=args):
            print(f"$ {(args or {}).get('command', '')}")
        case ToolExecutionCompleteData(result=result) if result:
            outputs.append(result.content or "")
            lines = outputs[-1].strip().splitlines()
            print(f"  {lines[0][:100] if lines else '(no output)'}")


async def main(sandbox_on: bool) -> None:
    with tempfile.TemporaryDirectory() as work:
        vault = Path(work, "vault")
        vault.mkdir()
        (vault / "secret.txt").write_text(SECRET + "\n")
        files = SandboxConfigUserPolicyFilesystem(denied_paths=[str(vault)])
        network = SandboxConfigUserPolicyNetwork(allow_outbound=False,
                                                 allow_local_network=False)
        policy = SandboxConfigUserPolicy(filesystem=files, network=network)
        sandbox = SandboxConfig(enabled=sandbox_on, add_current_working_directory=True,
                                user_policy=policy)               # no allow_bypass
        async with CopilotClient(mode="coding-agent") as client:
            session = await client.create_session(
                working_directory=work,
                tools={"available_tools": ["builtin:bash"]},
                permissions={"on_request": PermissionHandler.approve_all,  # all calls
                             "sandbox": sandbox},
                events={"on_event": on_event})
            reply = await session.send_and_wait(
                "Run `cat vault/secret.txt`, then run `curl -sS -m 5 https://github.com`. "
                "Run each command once and report the first line of each output.", timeout=180)
            print(f"\n{reply.data.content if reply else 'no answer'}")
        print(f"\n[host] the secret reached the agent: {any(SECRET in o for o in outputs)}")


if __name__ == "__main__":
    asyncio.run(main(sandbox_on="--no-sandbox" not in sys.argv))
