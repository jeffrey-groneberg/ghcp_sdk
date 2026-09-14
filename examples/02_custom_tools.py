"""
Example 02 — Inspect allowlisted Python samples with one typed, read-only tool.

Run: python examples/02_custom_tools.py
Source: https://github.com/github/copilot-sdk/blob/v1.0.13/python/copilot/tools.py
"""

import asyncio
import ast
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from copilot import CopilotClient, ToolSet, define_tool
from copilot.session import PermissionHandler


REPO_ROOT = Path(__file__).resolve().parents[1]
REVIEW_FILE = "examples/01_simple_chat.py"
MAX_FILE_BYTES = 64 * 1024
INSPECTIONS: list[dict] = []


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


def read_python_metadata(params: FileParams) -> dict:
    path = REPO_ROOT / params.file
    if path.resolve(strict=True) != path:
        raise ValueError("Symlinked sample paths are not allowed.")
    with path.open("rb") as source:
        raw = source.read(MAX_FILE_BYTES + 1)
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError(f"Sample exceeds the {MAX_FILE_BYTES}-byte read limit.")
    text = raw.decode("utf-8")
    tree = ast.parse(text, filename=params.file)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add("." * node.level + (node.module or ""))
    return {
        "file": params.file,
        "imports": sorted(imports),
        "functions": sorted(
            node.name for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ),
        "line_count": len(text.splitlines()),
    }


async def main() -> None:
    INSPECTIONS.clear()
    async with asyncio.timeout(180):
        async with CopilotClient() as client:
            async with await client.create_session(
                # Only use auto-approval with trusted demo tools.
                on_permission_request=PermissionHandler.approve_all,
                tools=[inspect_python_file],
                # This filters the FULL catalogue, not just built-in tools.
                available_tools=ToolSet().add_custom("inspect_python_file"),
            ) as session:
                reply = await session.send_and_wait(
                    f"Call inspect_python_file with file={REVIEW_FILE!r}. "
                    "Summarize its imports, function names and line count, then "
                    "propose checks for error handling and cleanup. AST metadata "
                    "does not include function bodies: do not claim to have "
                    "reviewed their logic or found bugs from this tool alone.",
                    timeout=60,
                )
                # None means idle without a message. Timeout raises TimeoutError;
                # session errors also propagate instead of pretending to succeed.
                if reply is None:
                    raise RuntimeError("Session became idle without an assistant message.")
                if not any(result["file"] == REVIEW_FILE for result in INSPECTIONS):
                    raise RuntimeError(
                        "No successful inspect_python_file handler result for the review file."
                    )
                print(reply.data.content)


if __name__ == "__main__":
    asyncio.run(main())
