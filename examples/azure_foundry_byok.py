"""
Slide 15 — The Microsoft Foundry BYOK example, with configurable credentials.

Run: python examples/azure_foundry_byok.py
Required: FOUNDRY_MODEL_URL, FOUNDRY_API_KEY, FOUNDRY_MODEL.
Source: https://github.com/github/copilot-sdk/blob/v1.0.13/docs/auth/byok.md
"""

import asyncio
import os
from urllib.parse import urlsplit

from copilot import CopilotClient
from copilot.session import ProviderConfig


def load_configuration() -> tuple[ProviderConfig, str]:
    names = ("FOUNDRY_MODEL_URL", "FOUNDRY_API_KEY", "FOUNDRY_MODEL")
    values = {name: os.environ.get(name, "").strip() for name in names}
    missing = [name for name in names if not values[name]]
    if missing:
        raise ValueError("Set the required BYOK environment variables: " + ", ".join(missing))
    url = values["FOUNDRY_MODEL_URL"]
    endpoint = urlsplit(url)
    if (
        endpoint.scheme != "https" or not endpoint.hostname
        or endpoint.username is not None or endpoint.password is not None
        or endpoint.query or endpoint.fragment
        or not endpoint.path.rstrip("/").endswith("/openai/v1")
    ):
        raise ValueError(
            "FOUNDRY_MODEL_URL must be an HTTPS Foundry endpoint ending in "
            "/openai/v1/, without credentials, query parameters, or fragments."
        )
    provider = ProviderConfig(
        type="openai",
        base_url=url.rstrip("/") + "/",
        api_key=values["FOUNDRY_API_KEY"],
        wire_api="responses",
    )
    return provider, values["FOUNDRY_MODEL"]


async def main() -> None:
    provider, model = load_configuration()
    async with asyncio.timeout(180):
        async with CopilotClient() as client:
            async with await client.create_session(
                provider=provider, available_tools=[], model=model,
            ) as session:
                reply = await session.send_and_wait("Hi", timeout=120)
                if reply is None:
                    raise RuntimeError("Session became idle without an assistant message.")
                print(reply.data.content)


if __name__ == "__main__":
    asyncio.run(main())
