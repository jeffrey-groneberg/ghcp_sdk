# 07 · Human in the loop

[Source](07_human_in_the_loop.py) · Python README: [permission handling](https://github.com/microsoft/copilot-sdk/blob/v2.0.1/python/README.md#permission-handling) and [user input requests](https://github.com/microsoft/copilot-sdk/blob/v2.0.1/python/README.md#user-input-requests)

The agent asks you a question, then wants to run one shell command. Your code
approves only that exact command, and only after you type `y`.

## Run it

```bash
python examples/07_human_in_the_loop.py
```

Type your name, then `y` or `n`.

## How it works

```python
session = await client.create_session(
    working_directory=work,
    tools={"available_tools": ToolSet().add_builtin(["ask_user", SHELL])},
    permissions={"on_request": on_permission},
    interaction={"on_user_input_request": on_user_input})
```

- `ask_user` is a built-in tool. `interaction.on_user_input_request` answers
  it; here it reads the terminal with `asyncio.to_thread(input, ...)`, so the
  event loop keeps running.
- `on_permission` rejects every command except `COMMAND` without asking you,
  and asks for `y` before it approves that one. `PermissionDecisionApproveOnce`
  and `PermissionDecisionReject` are experimental in SDK 2.0.1.
- The command writes `greeting.txt` in a temporary folder, so the host checks
  the result instead of trusting the model's report. The runtime runs commands
  it considers read-only, such as `echo` or `git status`, without a permission
  request.

## Output from a live run

```text
[agent asks] What is your name?
> Jeffrey

[approval] run `echo Hello from the Copilot SDK > greeting.txt`? [y/N] y
Hello, Jeffrey! Yes, the command ran and exited with code 0. It wrote "Hello from the Copilot SDK" to `greeting.txt`.
greeting.txt written: True
```

With `n`, the agent reports that the call was rejected, and the host prints
`greeting.txt written: False`.

## Watch out

- A real approval UI shows the exact request and defaults to "no", as this
  one does.
