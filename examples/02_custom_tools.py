"""
Example 02 — A custom tool with GitHub Copilot SDK 1.0.13.

Run: python examples/02_custom_tools.py
Source: https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/tools.py
"""

import asyncio
import random

from pydantic import BaseModel, Field

from copilot import CopilotClient, define_tool
from copilot.session import PermissionHandler


# Parameter names, types, descriptions and constraints form the model's schema.
class WeatherParams(BaseModel):
    city: str = Field(min_length=1, description="City name, e.g. 'Seattle'")


# This is deliberately a stub: label BOTH its description and output as fake.
# @define_tool replaces the function with a Tool carrying schema + handler.
@define_tool(description="Generate fictional demo weather for a city; NOT live weather")
async def get_weather(params: WeatherParams) -> dict:
    return {
        "city": params.city,
        "temperature_c": random.randint(-5, 35),
        "condition": random.choice(["sunny", "cloudy", "rainy"]),
        "source": "fictional demo data, not a live weather service",
    }


async def main() -> None:
    async with asyncio.timeout(180):
        async with CopilotClient() as client:
            async with await client.create_session(
                # Only use auto-approval with trusted demo tools.
                on_permission_request=PermissionHandler.approve_all,
                model="gpt-5-mini",
                tools=[get_weather],
                # This filters the FULL catalogue, not just built-in tools.
                available_tools=["custom:get_weather"],
            ) as session:
                reply = await session.send_and_wait(
                    "Use get_weather for fictional weather in Tokyo and Berlin. "
                    "Clearly label the result as demo data, not actual weather.",
                    timeout=60,
                )
                # None means idle without a message. Timeout raises TimeoutError;
                # session errors also propagate instead of pretending to succeed.
                if reply is None:
                    raise RuntimeError("Session became idle without an assistant message.")
                print(reply.data.content)


if __name__ == "__main__":
    asyncio.run(main())
