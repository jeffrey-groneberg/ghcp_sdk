"""
Bring your own model: a Microsoft Foundry deployment instead of Copilot models.

SDK 2.0 registers named provider connections under inference.providers;
github.capi.enabled=False keeps the session to your own models. Your provider
bills these calls, not GitHub Copilot. The key is never printed. Multi-provider
BYOK configuration (NamedProviderConfig) is experimental in SDK 2.0.1.

Set FOUNDRY_MODEL_URL (https://<resource>.openai.azure.com/openai/v1/),
FOUNDRY_API_KEY and FOUNDRY_MODEL (your deployment name), then
run: python examples/azure_foundry_byok.py
"""

import asyncio
import os
import sys

from copilot import CopilotClient

NAMES = ("FOUNDRY_MODEL_URL", "FOUNDRY_API_KEY", "FOUNDRY_MODEL")


async def main() -> None:
    url, key, model = (os.environ[name] for name in NAMES)
    async with CopilotClient(mode="coding-agent") as client:
        session = await client.create_session(
            model=model,
            github={"capi": {"enabled": False}},  # only your provider's models
            inference={"default_provider": "foundry",
                       "providers": [{"name": "foundry", "type": "openai", "base_url": url,
                                      "api_key": key, "wire_api": "responses"}]},
            tools={"available_tools": []})
        reply = await session.send_and_wait("Hi", timeout=120)
        print(reply.data.content if reply else "no answer")


if __name__ == "__main__":
    missing = [name for name in NAMES if not os.environ.get(name)]
    if missing:
        sys.exit("Set " + ", ".join(missing))
    asyncio.run(main())
