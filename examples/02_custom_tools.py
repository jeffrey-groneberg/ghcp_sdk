"""
Example 2: Custom Tools — Give Copilot access to your own functions.

Defines two tools (a weather API and a unit converter) that Copilot
can call automatically when the user's question requires them.

Prerequisites:
    pip install github-copilot-sdk pydantic
    Copilot CLI installed and signed in (or set COPILOT_GITHUB_TOKEN)

Usage:
    python 02_custom_tools.py
"""

import asyncio
import random

from copilot import CopilotClient, PermissionHandler
from copilot.generated.session_events import SessionEventType
from copilot.tools import define_tool
from pydantic import BaseModel, Field


# ── Tool 1: Weather lookup ──────────────────────────────────────
class WeatherParams(BaseModel):
    city: str = Field(description="City name, e.g. 'Seattle'")


@define_tool(description="Get the current weather for a given city")
async def get_weather(params: WeatherParams) -> dict:
    """Simulates a weather API call."""
    conditions = ["sunny", "cloudy", "rainy", "partly cloudy", "snowy"]
    temp_c = random.randint(-5, 35)
    return {
        "city": params.city,
        "temperature_c": temp_c,
        "temperature_f": round(temp_c * 9 / 5 + 32),
        "condition": random.choice(conditions),
        "humidity": f"{random.randint(30, 90)}%",
    }


# ── Tool 2: Unit converter ──────────────────────────────────────
class ConvertParams(BaseModel):
    value: float = Field(description="The numeric value to convert")
    from_unit: str = Field(description="Source unit, e.g. 'km'")
    to_unit: str = Field(description="Target unit, e.g. 'miles'")


@define_tool(description="Convert a value between common units (km/miles, kg/lbs, C/F)")
async def convert_units(params: ConvertParams) -> dict:
    """Handles a handful of common conversions."""
    conversions = {
        ("km", "miles"): lambda v: v * 0.621371,
        ("miles", "km"): lambda v: v / 0.621371,
        ("kg", "lbs"): lambda v: v * 2.20462,
        ("lbs", "kg"): lambda v: v / 2.20462,
        ("c", "f"): lambda v: v * 9 / 5 + 32,
        ("f", "c"): lambda v: (v - 32) * 5 / 9,
    }
    key = (params.from_unit.lower(), params.to_unit.lower())
    if key in conversions:
        result = round(conversions[key](params.value), 2)
        return {"value": params.value, "from": params.from_unit, "to": params.to_unit, "result": result}
    return {"error": f"Unsupported conversion: {params.from_unit} → {params.to_unit}"}


# ── Main ─────────────────────────────────────────────────────────
async def main():
    client = CopilotClient()
    await client.start()

    # Register both tools with the session
    session = await client.create_session(
        on_permission_request=PermissionHandler.approve_all,
        model="gpt-4.1",
        streaming=True,
        tools=[get_weather, convert_units],
    )

    # Print streaming output
    def on_event(event):
        if event.type == SessionEventType.ASSISTANT_MESSAGE_DELTA:
            print(event.data.delta_content, end="", flush=True)

    session.on(on_event)

    # Copilot will automatically call get_weather for each city
    prompt = "What's the weather in Tokyo, Berlin, and São Paulo? Show temperatures in both °C and °F."
    print(f"You: {prompt}\n")
    print("Copilot: ", end="")
    await session.send_and_wait(prompt)
    print("\n")

    # This one uses the unit converter tool
    prompt2 = "Convert 42 km to miles, and 185 lbs to kg."
    print(f"You: {prompt2}\n")
    print("Copilot: ", end="")
    await session.send_and_wait(prompt2)
    print("\n")

    await session.disconnect()
    await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
