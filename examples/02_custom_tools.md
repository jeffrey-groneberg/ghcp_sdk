# 02 · Custom tools

📖 **Sources (SDK v1.0.13):**
[Python tools](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/tools.py),
[session tool filters](https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/client.py),
[1.0.13 release](https://github.com/github/copilot-sdk/releases/tag/v1.0.13).

Open [the runnable source](02_custom_tools.py). A Pydantic schema describes
one custom function that returns **fictional weather**, not a live forecast.

## The flow

```mermaid
sequenceDiagram
    participant App
    participant Model
    participant Tool as get_weather handler
    App->>Model: prompt + registered tool schema
    Model->>Tool: city=Tokyo
    Tool-->>Model: random demo weather + explicit source label
    Model->>Tool: city=Berlin
    Tool-->>Model: random demo weather + explicit source label
    Model-->>App: assistant message; then idle
```

Tool choice and ordering are model decisions; the diagram illustrates a
possible run, not a guaranteed call schedule.

## Code walkthrough

### 1. Describe valid arguments

```python
class WeatherParams(BaseModel):
    city: str = Field(min_length=1, description="City name, e.g. 'Seattle'")
```

The schema includes field names, types, constraints and descriptions.
Descriptions help the model; they are not its only information. Pydantic
validates arguments before calling the decorated function.

### 2. Label the stub honestly

```python
@define_tool(description="Generate fictional demo weather for a city; NOT live weather")
async def get_weather(params: WeatherParams) -> dict:
    return {
        "city": params.city,
        "temperature_c": random.randint(-5, 35),
        "condition": random.choice(["sunny", "cloudy", "rainy"]),
        "source": "fictional demo data, not a live weather service",
    }
```

`@define_tool` produces a `Tool` with schema and handler; the decorated name
is no longer a plain Python function. Both synchronous and asynchronous
handlers are supported in 1.0.13. This example uses `async def` so a real
async API could replace the stub without blocking the event loop.

Return values are serialized for the model. Pydantic models are supported
directly (JSON-mode serialization was fixed in **1.0.9**); **1.0.13** also
handles native values such as dates, enums, UUIDs and decimals. A plain dict
keeps this workshop easy to read.

### 3. Register and scope the tool

```python
tools=[get_weather],
available_tools=["custom:get_weather"],
```

Registration and exposure are distinct. `available_tools` filters the
**entire merged catalogue**, including custom tools. Omitting the custom
name from a non-empty allowlist hides it. These source-qualified names are
documented by the [tagged ToolSet tests](https://github.com/github/copilot-sdk/blob/v1.0.13/python/test_tool_set.py).

`approve_all` is only for trusted demos. Actual business tools need
authorization, validation, credential isolation and side-effect controls.
An allowlist does not sandbox what your Python handler itself can do.

### 4. Wait for a final answer

The prompt explicitly asks for fictional weather and `send_and_wait` uses
`timeout=60`. Timeout raises `TimeoutError`; `None` means idle without an
assistant message, so the example raises instead of silently succeeding.
The whole operation has a 180-second deadline.

### 5. Respect cancellation

In 1.0.13, runtime completion/session termination cancels in-flight
**async external-tool tasks**. For a real HTTP/database tool, use async
I/O, `async with` and `finally`. Do not swallow `asyncio.CancelledError`;
cancellation does not undo a side effect already committed. Synchronous
blocking work is not magically interruptible.

## Run it

```bash
python examples/02_custom_tools.py
```

Illustrative output (random values and wording vary):

```text
Fictional demo weather, not a live forecast:
- Tokyo: sunny, 22°C
- Berlin: cloudy, 9°C
```

## Try this next

1. Replace randomness with fixed fixtures for deterministic exercises.
2. Add a temperature conversion tool and include its `custom:` name in the
   session allowlist.
3. Return a Pydantic response object and inspect its serialized tool result.
4. In a mocked test, cancel a sleeping async handler and verify its `finally`
   block runs.

## Common pitfalls

- A tool-call request in a prompt is not proof that the model called it.
- Blocking I/O inside `async def` still blocks the event loop.
- Concurrent handler calls must not corrupt shared mutable state.
- Tool exceptions become failure results; do not replace failures with fake
  successful business data. Test rejection/error paths as well as happy paths.
