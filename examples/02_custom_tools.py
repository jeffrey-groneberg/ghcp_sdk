"""
Example 02 — Custom tools

Tools are how you give the agent superpowers your app already has: database
lookups, internal APIs, fake-weather stubs, whatever. The agent decides
*when* to call them; you only have to declare *what* they do.

Concepts covered:
  * Declaring a tool with `@define_tool`
  * Describing parameters with a Pydantic `BaseModel` (the SDK uses this
    to build the JSON-Schema the model sees)
  * Wiring the tool into a session via the `tools=[...]` kwarg
  * Getting a one-shot reply with `send_and_wait` instead of streaming

Run:
    python examples/02_custom_tools.py
"""

import asyncio
import random

from pydantic import BaseModel, Field

from copilot import CopilotClient, define_tool
from copilot.session import PermissionHandler


# Pydantic models drive the JSON-Schema that's sent to the model. Use
# `Field(description=...)` for every argument — that text is the *only*
# hint the model gets about how to fill the parameter, so be specific.
class WeatherParams(BaseModel):
    city: str = Field(description="City name, e.g. 'Seattle'")


# `@define_tool` registers an async Python function as a callable tool.
# The `description` is the natural-language hint the model uses to decide
# whether the tool is relevant to the user's request — write it like a
# good docstring.
#
# The return value (any JSON-serializable object) is fed back to the model
# as the tool's result; here we return fake but realistic data.
@define_tool(description="Get the current weather for a given city")
async def get_weather(params: WeatherParams) -> dict:
    return {
        "city": params.city,
        "temperature_c": random.randint(-5, 35),
        "condition": random.choice(["sunny", "cloudy", "rainy"]),
    }


async def main() -> None:
    async with CopilotClient() as client:
        # `tools=[get_weather]` registers our tool for *this session only*.
        # The agent will see the tool definition in its system prompt and
        # decide on its own whether to call it.
        async with await client.create_session(
            on_permission_request=PermissionHandler.approve_all,
            model="gpt-4.1",
            tools=[get_weather],
        ) as session:

            # `send_and_wait` is the convenience shortcut for "send a prompt
            # and give me the final assistant message". It returns a single
            # event whose `.data.content` holds the plain-text reply, so it's
            # perfect for non-streaming, request/response style code.
            #
            # Under the hood it does what example 01 does manually: register
            # an event listener, wait for `SessionIdleData`, then return.
            reply = await session.send_and_wait(
                "What's the weather in Tokyo and Berlin?"
            )

            # `reply` is `None` if the timeout (default 60s) fires before the
            # agent finishes; otherwise it's an `AssistantMessage` event.
            if reply:
                print(reply.data.content)


if __name__ == "__main__":
    asyncio.run(main())
