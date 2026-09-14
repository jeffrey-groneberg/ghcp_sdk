# 02 · Inspect Python structure with a typed tool

**GitHub Copilot SDK - an introduction**

[Runnable source](02_custom_tools.py) · [Student guide](README.md)

**Sources, SDK v1.0.13:** [tool implementation](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/tools.py),
[tool-filter tests](https://github.com/github/copilot-sdk/blob/v1.0.13/python/test_tool_set.py).

## Goal and boundary

Obtain real structural facts about `examples/01_simple_chat.py` before
planning an error-handling and cleanup review. This checkpoint exposes **one
useful custom tool**, not a general filesystem API. It is independent of 01.

```mermaid
sequenceDiagram
    participant Host
    participant Runtime
    participant Handler as inspect_python_file
    Host->>Runtime: Register typed tool + custom-only allowlist
    Runtime->>Host: ToolInvocation(file=examples/01_simple_chat.py)
    Host->>Host: Pydantic validation
    Host->>Handler: Valid FileParams
    Handler->>Handler: Bound read; parse AST; record metadata
    Handler-->>Runtime: Deterministic JSON metadata
    Runtime-->>Host: Final assistant message
    Host->>Host: Require actual handler result for selected file
```

## Important code

The **actual function annotation** produces the SDK's JSON Schema:

```python
class FileParams(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    file: Literal[
        "examples/01_simple_chat.py", "examples/02_custom_tools.py"
    ] = Field(description="An explicitly allowlisted workshop Python file.")


@define_tool(description="Inspect an allowlisted Python sample's AST metadata")
async def inspect_python_file(params: FileParams) -> dict:
    metadata = read_python_metadata(params)
    INSPECTIONS.append(metadata)
    encoded = json.dumps(metadata, sort_keys=True)
    print("[host tool] inspect_python_file result=" + encoded)
    return metadata
```

`@define_tool` replaces the function with a `Tool` carrying its schema and
handler. It validates `ToolInvocation.arguments` with Pydantic before entering
the function. There is no hand-written schema that merely *looks* typed.

This complete schema-and-handler excerpt is 14 lines, including blank lines.
The ordinary `read_python_metadata(params: FileParams)` helper below it
contains the bounded file read and AST extraction. It is not another exposed
tool; the wrapper still records and logs the real handler result.

The host accepts exactly those two relative file names. Absolute paths,
traversal, glob patterns, other samples, wrong types, and extra parameters
fail validation. It rejects symlinked paths, reads at most
`MAX_FILE_BYTES + 1` bytes (`MAX_FILE_BYTES = 64 * 1024`), and fails if the
limit is exceeded, decoding fails, or Python syntax is invalid.

The returned dictionary has exactly four keys:

| Key | Deterministic value |
|---|---|
| `file` | The validated repository-relative path |
| `imports` | Sorted unique imported module names, including relative prefixes |
| `functions` | Sorted function names from the AST, including async/nested functions |
| `line_count` | Number of source lines |

The handler records each successful dictionary in `INSPECTIONS` and prints
`[host tool] inspect_python_file result=...`. `main()` clears this process-local
list before the run and rejects a final answer without a successful result
for the requested file. Model prose cannot populate that list.

```python
tools=[inspect_python_file],
available_tools=ToolSet().add_custom("inspect_python_file"),
```

Registration and exposure are different: the session filter applies to the
whole merged catalogue, not only built-ins. No shell or general `view` tool
is available here.

AST metadata does **not** contain function bodies. The prompt asks for
structural facts and proposed checks, not claims of discovered logic bugs.
This handler runs in host Python; a tool allowlist does not sandbox it.
Use this bounded reader only in a trusted workshop checkout, not as a
multi-user filesystem security boundary.

## Run and inspect

```bash
python examples/02_custom_tools.py
```

**Illustrative output shape, not an observed run; the line count follows the
current file:**

```text
[host tool] inspect_python_file result={"file": "examples/01_simple_chat.py", "functions": ["main", "on_event"], "imports": [...], "line_count": <actual integer>}
<Assistant summarizes the returned structure and suggests review checks.>
```

The offline suite invokes the real decorated SDK handler, compares repeated
results, checks the generated schema and validated helper delegation, and
covers path/size/syntax failures. An AST-based check bounds the declaration
excerpt to 14 lines and ensures this walkthrough quotes it exactly.
The conversation still requires a final message and bounded cleanup.

**Exercise:** ask for `../README.md`. Inspect the validation failure; do not
widen the tool into an unrestricted file reader to make the request work.
