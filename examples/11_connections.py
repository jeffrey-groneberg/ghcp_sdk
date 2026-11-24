"""
Example 11: pick the connection, keep the code (deck slide 29).

One program, three connections; only the runtime argument changes.
  inprocess  the 2.0 default: the runtime loads into this process (not a sandbox)
  stdio      the runtime as a child process (the 1.x default)
  server     a shared runtime server that you start first:
             copilot-runtime --server --port 4321  (see 11_connections.md)

Run:
    python examples/11_connections.py inprocess
    python examples/11_connections.py stdio
    python examples/11_connections.py server
"""

import asyncio
import sys

from copilot import CopilotClient, RuntimeConnection

CONNECTIONS = {
    "inprocess": lambda: None,                               # 2.0 default
    "stdio": lambda: RuntimeConnection.for_spawned_stdio(),  # 1.x default
    "server": lambda: RuntimeConnection.for_tcp("localhost", 4321),
}


async def main(conn: str) -> None:
    client = CopilotClient(mode="coding-agent", runtime=CONNECTIONS[conn]())
    await client.start()
    try:
        status = await client.get_status()
        print(f"{conn}: {status.version}, protocol {status.protocol_version}")
        session = await client.create_session(tools={"available_tools": []})
        reply = await session.send_and_wait("Reply with the word: connected", timeout=60)
        print(reply.data.content if reply else "no answer")
    finally:
        await client.stop()


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in CONNECTIONS:
        sys.exit("usage: python examples/11_connections.py inprocess|stdio|server")
    asyncio.run(main(sys.argv[1]))
