"""Offline tests: no sign-in, no runtime, no model call.

Run: python -m unittest discover -s examples/tests -v
"""

import contextlib
import importlib.util
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace, UnionType
from typing import Union, get_args, get_origin, get_type_hints, is_typeddict
from unittest.mock import AsyncMock, patch

import copilot
from copilot.rpc import PermissionDecisionApproveOnce, PermissionDecisionReject

EXAMPLES = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXAMPLES))

RUNS = [
    ("01_simple_chat",), ("02_custom_tools",), ("03_custom_agents",), ("04_hooks",),
    ("05_mcp_servers",), ("06_session_resume", "create", "s1"), ("06_session_resume", "resume", "s1"),
    ("07_human_in_the_loop",), ("08_sandbox",), ("09_events",), ("10_identity",),
    ("11_connections", "inprocess"), ("11_connections", "stdio"), ("11_connections", "server"),
    ("12_approval",), ("13_containment", True), ("13_containment", False),
    ("14_session_fs", "create"), ("14_session_fs", "resume"), ("15_cost",), ("16_skills",),
    ("azure_foundry_byok",),
]

# The SDK's own signatures and option types are the reference for every option.
SCHEMAS = {
    "client": get_type_hints(copilot.CopilotClient.__init__),
    "create": get_type_hints(copilot.CreateSessionOptions),
    "resume": get_type_hints(copilot.ResumeSessionOptions),
}


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, EXAMPLES / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def unknown_keys(value, hint, path: str) -> list[str]:
    """Keys in value, at any depth, that the SDK's type hint doesn't define."""
    options = get_args(hint) if get_origin(hint) in (Union, UnionType) else (hint,)
    typed = [t for t in options if is_typeddict(t)]
    if typed and isinstance(value, dict):
        fields = {}
        for t in typed:
            fields.update(get_type_hints(t))
        return [problem for key, item in value.items()
                for problem in ([path + key] if key not in fields
                                else unknown_keys(item, fields[key], f"{path}{key}."))]
    for option in options:
        origin, args = get_origin(option), get_args(option)
        if origin is list and isinstance(value, list):
            return [p for item in value for p in unknown_keys(item, args[0], path)]
        if origin is dict and isinstance(value, dict):
            return [p for item in value.values() for p in unknown_keys(item, args[1], path)]
    return []


def unknown_options(kind: str, options: dict) -> list[str]:
    hints = SCHEMAS[kind]
    return [problem for name, value in options.items()
            for problem in ([name] if name not in hints
                            else unknown_keys(value, hints[name], f"{name}."))]


class FakeSession:
    session_id = "fake-session"

    def __init__(self):
        self.rpc = SimpleNamespace(
            agent=SimpleNamespace(select=AsyncMock()),
            git_hub_auth=SimpleNamespace(get_status=AsyncMock(
                return_value=SimpleNamespace(is_authenticated=True, auth_type=None))),
            usage=SimpleNamespace(get_metrics=AsyncMock(return_value=SimpleNamespace(
                total_nano_aiu=0, ai_credits_status=None, total_premium_request_cost=0))))

    async def send_and_wait(self, prompt, timeout=60):
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None


class FakeClient:
    calls: list[tuple[str, dict]] = []

    def __init__(self, **options):
        self.calls.append(("client", options))

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def start(self):
        return None

    async def stop(self):
        return None

    async def get_status(self):
        return SimpleNamespace(version="test", protocol_version=4)

    async def get_auth_status(self):
        return SimpleNamespace(is_authenticated=False)

    async def create_session(self, **options):
        self.calls.append(("create", options))
        return FakeSession()

    async def resume_session(self, session_id, **options):
        self.calls.append(("resume", options))
        return FakeSession()


class ExamplesUseSdk2OptionsTest(unittest.IsolatedAsyncioTestCase):
    async def test_every_example_passes_only_sdk_2_0_options(self):
        for name, *args in RUNS:
            with self.subTest(example=name, args=args), tempfile.TemporaryDirectory() as tmp:
                module = load(name)
                FakeClient.calls = []
                with contextlib.ExitStack() as stack:
                    stack.enter_context(patch.object(module, "CopilotClient", FakeClient))
                    stack.enter_context(patch("subprocess.check_output", return_value="token\n"))
                    stack.enter_context(patch.dict(os.environ, {
                        "FOUNDRY_MODEL_URL": "https://example.invalid/openai/v1/",
                        "FOUNDRY_API_KEY": "key", "FOUNDRY_MODEL": "model"}))
                    stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                    if hasattr(module, "make_demo_repo"):
                        stack.enter_context(patch.object(module, "make_demo_repo", return_value=Path(tmp)))
                    if hasattr(module, "STORE"):
                        stack.enter_context(patch.object(module, "STORE", Path(tmp, "store")))
                    await module.main(*args)
                kinds = [kind for kind, _ in FakeClient.calls]
                self.assertEqual(kinds[0], "client")
                self.assertTrue({"create", "resume"} & set(kinds), "no session was opened")
                self.assertIn(FakeClient.calls[0][1].get("mode"), get_args(SCHEMAS["client"]["mode"]))
                for kind, options in FakeClient.calls:
                    self.assertEqual(unknown_options(kind, options), [], kind)


def shell(command: str):
    return SimpleNamespace(full_command_text=command)


class ApprovalTest(unittest.IsolatedAsyncioTestCase):
    async def test_12_block_list_misses_a_variant_the_exact_match_rejects(self):
        m = load("12_approval")
        with contextlib.redirect_stdout(io.StringIO()):
            denied = await m.pre_tool_use({"toolArgs": {"command": "rm -rf build"}}, {})
            self.assertEqual(denied["permissionDecision"], "deny")
            self.assertIsNone(await m.pre_tool_use({"toolArgs": {"command": "rm -r -f build"}}, {}))
            self.assertIsInstance(m.on_permission(shell("git status"), {}), PermissionDecisionApproveOnce)
            for request in (shell("rm -r -f build"), shell("git status --short"), SimpleNamespace(path="/etc")):
                self.assertIsInstance(m.on_permission(request, {}), PermissionDecisionReject)

    async def test_07_asks_a_human_only_for_the_exact_command(self):
        m = load("07_human_in_the_loop")
        with contextlib.redirect_stdout(io.StringIO()):
            with patch("builtins.input", side_effect=AssertionError("must not ask")):
                self.assertIsInstance(await m.on_permission(shell("rm -rf /"), {}), PermissionDecisionReject)
            for answer, expected in (("y", PermissionDecisionApproveOnce), ("n", PermissionDecisionReject),
                                     ("", PermissionDecisionReject)):
                with patch("builtins.input", return_value=answer):
                    self.assertIsInstance(await m.on_permission(shell(m.COMMAND), {}), expected)

    async def test_08_asks_a_human_only_for_a_sandbox_bypass(self):
        m = load("08_sandbox")
        with patch("builtins.input", side_effect=AssertionError("must not ask")):
            inside = SimpleNamespace(request_sandbox_bypass=False, path="/work")
            self.assertIsInstance(await m.on_permission(inside, {}), PermissionDecisionApproveOnce)
        bypass = SimpleNamespace(request_sandbox_bypass=True, path="/work/vault")
        for answer, expected in (("y", PermissionDecisionApproveOnce), ("n", PermissionDecisionReject)):
            with patch("builtins.input", return_value=answer):
                self.assertIsInstance(await m.on_permission(bypass, {}), expected)


class SessionFsTest(unittest.IsolatedAsyncioTestCase):
    async def test_14_store_keeps_each_sessions_files_in_its_own_folder(self):
        m = load("14_session_fs")
        with tempfile.TemporaryDirectory() as tmp, patch.object(m, "STORE", Path(tmp)):
            fs = m.FolderFs("s1")
            await fs.write_file("/session-state/checkpoints/index.md", "# index")
            await fs.write_file("/session-state/events.jsonl", "a\n")
            await fs.append_file("/session-state/events.jsonl", "b\n")
            entries = {e.name: e.type.value for e in await fs.readdir_with_types("/session-state")}
            self.assertEqual(entries, {"checkpoints": "directory", "events.jsonl": "file"})
            await fs.write_file("/session-state/events.tmp", "c\n")
            await fs.rename("/session-state/events.tmp", "/session-state/events.jsonl")

            resumed = m.FolderFs("s1")  # a new process opens the same store
            self.assertEqual(await resumed.read_file("/session-state/events.jsonl"), "c\n")
            self.assertFalse(await m.FolderFs("s2").exists("/session-state/events.jsonl"))
            with self.assertRaises(PermissionError):
                await resumed.read_file("/../s2/session-state/events.jsonl")
            await resumed.rm("/session-state", recursive=True, force=False)
            with self.assertRaises(FileNotFoundError):
                await resumed.read_file("/session-state/checkpoints/index.md")


if __name__ == "__main__":
    unittest.main()
