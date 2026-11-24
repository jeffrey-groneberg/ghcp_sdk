"""
Example 02: hand the agent a Python function (deck slide 19).

A typed custom tool runs in your process. Its Pydantic model and description
become the schema the model sees. The data is fictional.

Run: python examples/02_custom_tools.py
"""

import asyncio

from pydantic import BaseModel, Field

from copilot import CopilotClient, ToolSet, define_tool


class BuildParams(BaseModel):
    build_id: int = Field(description="CI build number")


@define_tool(description="Failed tests of CI build", skip_permission=True)  # read-only
async def get_failed_tests(params: BuildParams) -> dict:
    return {"build": params.build_id, "failed": ["test_login"],  # fictional demo data
            "error": "TimeoutError: auth service timed out after 30 s"}


async def main() -> None:
    async with CopilotClient(mode="coding-agent") as client:
        session = await client.create_session(tools={
            "definitions": [get_failed_tests],  # registers the handler
            "available_tools": ToolSet().add_custom("get_failed_tests")})
        reply = await session.send_and_wait(
            "Why did build 4711 fail? Answer in two sentences.", timeout=120)
        print(reply.data.content if reply else "no answer")


if __name__ == "__main__":
    asyncio.run(main())
