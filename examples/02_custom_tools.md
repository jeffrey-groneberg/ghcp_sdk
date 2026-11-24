# 02 · Custom tool

Deck slide 19 · [Source](02_custom_tools.py) · [Tools in the Python README](https://github.com/microsoft/copilot-sdk/blob/v2.0.1/python/README.md#tools)

A custom tool is a typed Python function that runs in your process. This one
returns fictional CI results.

## Run it

```bash
python examples/02_custom_tools.py
```

## How it works

```python
@define_tool(description="Failed tests of CI build", skip_permission=True)  # read-only
async def get_failed_tests(params: BuildParams) -> dict:
    ...
session = await client.create_session(tools={
    "definitions": [get_failed_tests],  # registers the handler
    "available_tools": ToolSet().add_custom("get_failed_tests")})
```

- The Pydantic model `BuildParams` and the description become the schema the
  model sees. The SDK validates the model's arguments before it calls your
  function.
- `skip_permission=True` runs the tool without a permission request. Use it
  only for tools that just read.
- `tools.definitions` registers the handler, and `tools.available_tools`
  exposes exactly this tool. The allow-list filters the whole catalog:
  built-in (`builtin:`), MCP (`mcp:`) and your own (`custom:`) tools.

## Output from a live run

```text
Build 4711 failed because `test_login` was the only failing test. It hit a `TimeoutError` when the auth service didn't respond within 30 seconds. ...
```

## Try this next

- Ask about build 4712. The tool returns the same fictional data, and the
  model trusts it: the model chooses the tool, and your code supplies the facts.
