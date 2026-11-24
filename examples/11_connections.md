# 11 · Connections

Deck slide 29 · [Source](11_connections.py) · [In-process runtime](https://github.com/microsoft/copilot-sdk/blob/v2.0.1/docs/setup/in-process-runtime.md) · [Backend services](https://github.com/microsoft/copilot-sdk/blob/v2.0.1/docs/setup/backend-services.md)

One program, three ways to reach the runtime. Only the `runtime` argument
changes.

## Run it

```bash
python examples/11_connections.py inprocess
python examples/11_connections.py stdio
python examples/11_connections.py server     # start the runtime server first
```

For `server`, start the runtime that the SDK caches, in another terminal:

```bash
RUNTIME=$(python -m copilot download-runtime | sed -n 's/^Runtime cached at: //p')
"$RUNTIME" --server --port 4321      # prints: CLI server listening on port 4321
```

## How it works

```python
CONNECTIONS = {
    "inprocess": lambda: None,                               # 2.0 default
    "stdio": lambda: RuntimeConnection.for_spawned_stdio(),  # 1.x default
    "server": lambda: RuntimeConnection.for_tcp("localhost", 4321),
}
client = CopilotClient(mode="coding-agent", runtime=CONNECTIONS[conn]())
```

| Connection | What runs where |
|---|---|
| In process (no `runtime`) | The 2.0 default: the runtime loads into your process. It isn't a sandbox and gives no crash isolation. |
| `for_spawned_stdio()` | The 1.x default: a child process your client starts and stops. |
| `for_tcp(host, port)` | A shared `copilot-runtime --server` that many clients use, each session with its own token. |

- A client attached over TCP can't set the runtime's startup options, such as
  `github.token`; configure those on the server.
- The server listens only on 127.0.0.1. Serving other hosts takes `--host` and a
  connection token: `COPILOT_CONNECTION_TOKEN` on the server and
  `connection_token=` in `for_tcp`.
- `COPILOT_SDK_DEFAULT_CONNECTION=stdio` switches the default without a code change.

## Output from a live run

```text
inprocess: 1.0.114, protocol 4
connected
stdio: 1.0.114, protocol 4
connected
server: 1.0.114, protocol 4
connected
```
