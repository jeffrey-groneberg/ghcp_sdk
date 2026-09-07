"""Offline regression tests: real SDK types, mocked runtime and human input.

Run: python -m unittest discover -s examples/tests -v
No Copilot runtime, model prompt, authentication lookup or shell tool is run.
"""

import asyncio
import contextlib
import importlib.util
import inspect
import io
import json
from pathlib import Path
import subprocess
import sys
import tomllib
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from copilot import CopilotClient, RuntimeConnection
from copilot.rpc import AgentSelectRequest, PermissionDecisionApproveOnce, PermissionDecisionReject
from copilot.session import CopilotSession, ProviderConfig, SessionHooks
from copilot.session_events import (
    AssistantMessageData,
    AssistantMessageDeltaData,
    PermissionRequestRead,
    PermissionRequestShell,
    SessionErrorData,
    SessionIdleData,
    ToolExecutionStartData,
)
from copilot.tools import ToolInvocation


ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_FILES = sorted((ROOT / "examples").glob("0[1-7]_*.py"))


def load_example(path):
    spec = importlib.util.spec_from_file_location(f"example_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


EXAMPLES = [load_example(path) for path in EXAMPLE_FILES]


def event(data):
    return SimpleNamespace(type="test", data=data)


def final_reply():
    return event(AssistantMessageData(content="Mocked assistant response", message_id="message-1"))


class FakeSession:
    def __init__(self):
        self.session_id = "test-session"
        self.entered = self.exited = False
        self.listeners = []
        self.unsubscribed = 0
        self.send_and_wait = AsyncMock(return_value=final_reply())
        self.rpc = SimpleNamespace(agent=SimpleNamespace(
            list=AsyncMock(return_value=SimpleNamespace(
                agents=[SimpleNamespace(name="researcher"), SimpleNamespace(name="reviewer")],
            )),
            get_current=AsyncMock(side_effect=[
                SimpleNamespace(agent=SimpleNamespace(name="researcher")),
                SimpleNamespace(agent=SimpleNamespace(name="reviewer")),
            ]),
            select=AsyncMock(),
        ))

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, *_):
        self.exited = True

    def on(self, callback):
        self.listeners.append(callback)

        def unsubscribe():
            self.listeners.remove(callback)
            self.unsubscribed += 1

        return unsubscribe

    def emit(self, data):
        for callback in list(self.listeners):
            callback(event(data))


class FakeClient:
    def __init__(self):
        self.session = FakeSession()
        self.entered = self.exited = False
        self.constructor_options = self.session_options = None
        self.resumed_id = None

    def factory(self, **kwargs):
        inspect.signature(CopilotClient).bind(**kwargs)
        self.constructor_options = kwargs
        return self

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, *_):
        self.exited = True

    async def create_session(self, **kwargs):
        inspect.signature(CopilotClient.create_session).bind(self, **kwargs)
        self.session_options = kwargs
        return self.session

    async def resume_session(self, session_id, **kwargs):
        inspect.signature(CopilotClient.resume_session).bind(self, session_id, **kwargs)
        self.resumed_id = session_id
        self.session_options = kwargs
        return self.session


class PrototypeTests(unittest.IsolatedAsyncioTestCase):
    async def run_example(self, module, client, *args):
        output = io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(module, "CopilotClient", client.factory))
            if hasattr(module, "github_token"):
                stack.enter_context(patch.object(module, "github_token", return_value="test-secret"))
            stack.enter_context(contextlib.redirect_stdout(output))
            await module.main(*args)
        return output.getvalue()

    async def test_all_seven_use_valid_sdk_options_and_cleanup(self):
        self.assertEqual(len(EXAMPLES), 7)
        for module in EXAMPLES:
            with self.subTest(example=module.__name__):
                client = FakeClient()
                await self.run_example(module, client)
                self.assertTrue(client.entered and client.exited)
                self.assertTrue(client.session.entered and client.session.exited)
                self.assertEqual(client.session_options["model"], "gpt-5-mini")
                self.assertIn("available_tools", client.session_options)
                for call in client.session.send_and_wait.await_args_list:
                    self.assertGreater(call.kwargs["timeout"], 0)
                self.assertEqual(client.session.listeners, [])

    async def test_all_seven_propagate_timeout_error_and_cancellation(self):
        for module in EXAMPLES:
            for failure in (TimeoutError("deadline"), RuntimeError("runtime failed"),
                            asyncio.CancelledError()):
                with self.subTest(example=module.__name__, failure=type(failure).__name__):
                    client = FakeClient()
                    client.session.send_and_wait.side_effect = failure
                    with self.assertRaises(type(failure)):
                        await self.run_example(module, client)
                    self.assertTrue(client.session.exited and client.exited)
                    self.assertEqual(client.session.listeners, [])

    async def test_all_seven_reject_missing_final_reply(self):
        for module in EXAMPLES:
            with self.subTest(example=module.__name__):
                client = FakeClient()
                client.session.send_and_wait.return_value = None
                with self.assertRaisesRegex(RuntimeError, "without an assistant message"):
                    await self.run_example(module, client)
                self.assertTrue(client.exited)

    async def test_streaming_and_new_client_identity(self):
        client = FakeClient()

        async def reply(*_, **__):
            client.session.emit(AssistantMessageDeltaData(delta_content="Hello", message_id="m"))
            client.session.emit(AssistantMessageDeltaData(delta_content=" world", message_id="m"))
            return final_reply()

        client.session.send_and_wait.side_effect = reply
        output = await self.run_example(EXAMPLES[0], client)
        self.assertEqual(output, "Hello world\n")
        self.assertEqual(client.session.unsubscribed, 1)
        self.assertEqual(client.session_options["available_tools"], [])
        self.assertEqual(client.constructor_options["client_info"]["application_name"],
                         "ghcp-sdk-examples")
        self.assertEqual(client.constructor_options["client_info"]["integration_version"], "1.0.13")

    async def test_agent_switch_uses_typed_request_and_checks_state(self):
        client = FakeClient()
        await self.run_example(EXAMPLES[2], client)
        selected = client.session.rpc.agent.select.await_args.args[0]
        self.assertIsInstance(selected, AgentSelectRequest)
        self.assertEqual(selected.name, "reviewer")
        self.assertEqual(client.session.send_and_wait.await_count, 2)
        for missing in (None, SimpleNamespace(name="wrong-agent")):
            client = FakeClient()
            client.session.rpc.agent.get_current.side_effect = [
                SimpleNamespace(agent=SimpleNamespace(name="researcher")),
                SimpleNamespace(agent=missing),
            ]
            with self.assertRaisesRegex(RuntimeError, "reviewer persona"):
                await self.run_example(EXAMPLES[2], client)
            self.assertEqual(client.session.send_and_wait.await_count, 1)

    async def test_hooks_only_log_tool_names(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            for name in ("on_pre_tool_use", "on_post_tool_use", "on_post_tool_use_failure"):
                result = await getattr(EXAMPLES[3], name)(
                    {"toolName": "view", "toolArgs": "test-secret", "toolResult": "test-secret"},
                    {"session_id": "test"},
                )
                self.assertIsNone(result)
        self.assertIn("[pre]  view", output.getvalue())
        self.assertIn("[post] view succeeded", output.getvalue())
        self.assertIn("[failed] view", output.getvalue())
        self.assertNotIn("test-secret", output.getvalue())
        client = FakeClient()
        await self.run_example(EXAMPLES[3], client)
        self.assertIn("on_post_tool_use_failure", client.session_options["hooks"])

    async def test_mcp_names_filters_and_safe_event_trace(self):
        client = FakeClient()

        async def reply(*_, **__):
            client.session.emit(ToolExecutionStartData(
                tool_call_id="tool-1", tool_name="github-list_issues",
                mcp_server_name="github", mcp_tool_name="list_issues",
                arguments={"private": "test-secret"},
            ))
            return final_reply()

        client.session.send_and_wait.side_effect = reply
        output = await self.run_example(EXAMPLES[4], client)
        server = client.session_options["mcp_servers"]["github"]
        self.assertEqual(server["tools"], ["list_issues", "issue_read", "search_issues"])
        self.assertEqual(server["headers"]["X-MCP-Readonly"], "true")
        self.assertEqual(server["headers"]["Authorization"], "Bearer test-secret")
        self.assertEqual(client.session_options["available_tools"],
                         [f"mcp:github-{name}" for name in server["tools"]])
        self.assertIn("[mcp] github/list_issues", output)
        self.assertNotIn("test-secret", output)

    async def test_resume_resupplies_scope_without_repeating_facts(self):
        client = FakeClient()
        output = await self.run_example(EXAMPLES[5], client, True, "saved-conversation")
        self.assertEqual(client.resumed_id, "saved-conversation")
        self.assertNotIn("model", client.session_options)
        self.assertEqual(client.session_options["available_tools"], [])
        self.assertIn("on_permission_request", client.session_options)
        prompt = client.session.send_and_wait.await_args.args[0]
        self.assertNotIn("Jeffrey", prompt)
        self.assertNotIn("Python", prompt)
        self.assertIn("test-session", output)

    async def test_legacy_input_variant_and_scoped_shell(self):
        client = FakeClient()
        await self.run_example(EXAMPLES[6], client)
        self.assertEqual(client.session_options["ask_user_variant"], "legacy")
        self.assertIs(client.session_options["on_user_input_request"],
                      EXAMPLES[6].on_user_input_request)
        self.assertEqual(len(client.session_options["available_tools"]), 2)


class ToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_weather_schema_and_fictional_results(self):
        tool = EXAMPLES[1].get_weather
        self.assertEqual(tool.parameters["required"], ["city"])
        self.assertEqual(tool.parameters["properties"]["city"]["minLength"], 1)
        with patch.object(EXAMPLES[1].random, "randint", return_value=21), \
             patch.object(EXAMPLES[1].random, "choice", return_value="sunny"):
            result = await tool.handler(ToolInvocation(arguments={"city": "Tokyo"}))
        self.assertEqual(result.result_type, "success")
        data = json.loads(result.text_result_for_llm)
        self.assertEqual((data["city"], data["temperature_c"]), ("Tokyo", 21))
        self.assertIn("fictional", data["source"])

    async def test_weather_schema_rejects_empty_city(self):
        result = await EXAMPLES[1].get_weather.handler(ToolInvocation(arguments={"city": ""}))
        self.assertEqual(result.result_type, "failure")


class TokenTests(unittest.TestCase):
    def test_import_never_resolves_credentials_or_starts_client(self):
        with patch("subprocess.check_output") as lookup, patch.object(CopilotClient, "start") as start:
            for path in EXAMPLE_FILES:
                load_example(path)
        lookup.assert_not_called()
        start.assert_not_called()

    def test_environment_precedence_and_whitespace(self):
        for env, expected in (
            ({"GITHUB_TOKEN": " first ", "GH_TOKEN": "second"}, "first"),
            ({"GITHUB_TOKEN": "  ", "GH_TOKEN": " second "}, "second"),
        ):
            with self.subTest(env=list(env)), patch.dict("os.environ", env, clear=True), \
                 patch("subprocess.check_output") as lookup:
                self.assertEqual(EXAMPLES[4].github_token(), expected)
                lookup.assert_not_called()

    def test_gh_fallback_is_host_specific_bounded_and_secret_safe(self):
        with patch.dict("os.environ", {}, clear=True), \
             patch("subprocess.check_output", return_value=" token \n") as lookup:
            self.assertEqual(EXAMPLES[4].github_token(), "token")
        self.assertEqual(lookup.call_args.args[0], ["gh", "auth", "token", "--hostname", "github.com"])
        self.assertEqual(lookup.call_args.kwargs["timeout"], 10)
        self.assertIs(lookup.call_args.kwargs["stderr"], subprocess.DEVNULL)

    def test_token_failures_are_clear_without_secret_output(self):
        failures = (
            FileNotFoundError(),
            subprocess.CalledProcessError(1, "gh", output="private-token"),
            subprocess.TimeoutExpired("gh", 10, output="private-token"),
        )
        for failure in failures:
            with self.subTest(failure=type(failure).__name__), \
                 patch.dict("os.environ", {}, clear=True), \
                 patch("subprocess.check_output", side_effect=failure):
                with self.assertRaises(RuntimeError) as raised:
                    EXAMPLES[4].github_token()
                self.assertNotIn("private-token", str(raised.exception))
                self.assertTrue(raised.exception.__suppress_context__)
        with patch.dict("os.environ", {}, clear=True), \
             patch("subprocess.check_output", return_value=" \n"):
            with self.assertRaisesRegex(RuntimeError, "empty token"):
                EXAMPLES[4].github_token()


class HumanInputTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.module = EXAMPLES[6]
        self.module.INPUT_LOCK = asyncio.Lock()
        self.module.INPUT_CLOSED = False
        self.shell = PermissionRequestShell(
            can_offer_session_approval=False, commands=[], full_command_text="echo hello",
            has_write_file_redirection=False, intention="greet", possible_paths=[], possible_urls=[],
        )

    async def test_choice_numbers_labels_and_freeform(self):
        cases = (
            ({"choices": ["English", "German"], "allowFreeform": False}, "2", "German", False),
            ({"choices": ["English", "German"], "allowFreeform": False}, "English", "English", False),
            ({"choices": ["English"], "allowFreeform": True}, "French", "French", True),
            ({}, "Ada", "Ada", True),
        )
        for request, answer, expected, freeform in cases:
            with self.subTest(answer=answer), \
                 patch.object(self.module, "read_answer", AsyncMock(return_value=answer)), \
                 contextlib.redirect_stdout(io.StringIO()):
                result = await self.module.on_user_input_request(request, {})
                self.assertEqual(result, {"answer": expected, "wasFreeform": freeform})

    async def test_invalid_choices_retry_and_stop(self):
        with patch.object(self.module, "read_answer",
                          AsyncMock(side_effect=["9", "other", ""])) as reader, \
             contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, "three attempts"):
                await self.module.on_user_input_request(
                    {"choices": ["English"], "allowFreeform": False}, {},
                )
        self.assertEqual(reader.await_count, 3)
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, "neither choices"):
                await self.module.on_user_input_request({"allowFreeform": False}, {})

    async def test_permission_approval_denial_and_unavailable_input(self):
        for answer, expected in (("y", PermissionDecisionApproveOnce),
                                 ("N", PermissionDecisionReject), ("", PermissionDecisionReject)):
            with self.subTest(answer=answer), \
                 patch.object(self.module, "read_answer", AsyncMock(return_value=answer)), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertIsInstance(await self.module.on_permission_request(self.shell, {}), expected)
        for failure in (TimeoutError(), EOFError(), OSError()):
            with patch.object(self.module, "read_answer", AsyncMock(side_effect=failure)), \
                 contextlib.redirect_stdout(io.StringIO()), \
                 contextlib.redirect_stderr(io.StringIO()) as error:
                result = await self.module.on_permission_request(self.shell, {})
                self.assertIsInstance(result, PermissionDecisionReject)
                self.assertIn("denied", error.getvalue())

    async def test_reads_are_not_automatically_trusted(self):
        with patch.object(self.module, "read_answer") as reader, \
             contextlib.redirect_stdout(io.StringIO()):
            result = await self.module.on_permission_request(
                PermissionRequestRead(intention="read", path="private-file"), {},
            )
        self.assertIsInstance(result, PermissionDecisionReject)
        reader.assert_not_called()

    async def test_callbacks_propagate_cancellation(self):
        for callback, request in (
            (self.module.on_user_input_request, {"question": "Name?"}),
            (self.module.on_permission_request, self.shell),
        ):
            with patch.object(self.module, "read_answer", AsyncMock(side_effect=asyncio.CancelledError)), \
                 contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(asyncio.CancelledError):
                    await callback(request, {})

    async def test_console_reader_success_eof_and_timeout(self):
        with patch("builtins.input", return_value=" Ada "):
            self.assertEqual(await self.module.read_answer("Name: "), "Ada")
        with patch("builtins.input", side_effect=EOFError):
            with self.assertRaises(EOFError):
                await self.module.read_answer("Name: ")
        self.assertTrue(self.module.INPUT_CLOSED)
        self.module.INPUT_CLOSED = False
        with patch.object(self.module, "INPUT_TIMEOUT", 0.001), \
             patch.object(self.module.threading, "Thread") as thread:
            with self.assertRaises(TimeoutError):
                await self.module.read_answer("Name: ")
            self.assertTrue(thread.call_args.kwargs["daemon"])
            with self.assertRaises(EOFError):
                await self.module.read_answer("Don't start another reader: ")
            self.assertEqual(thread.call_count, 1)


class SDKContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_send_and_wait_timeout_and_listener_cleanup(self):
        session = CopilotSession("test", Mock())
        session.send = AsyncMock()
        with self.assertRaises(TimeoutError):
            await session.send_and_wait("mock", timeout=0.001)
        self.assertFalse(session._event_handlers)

    async def test_real_send_and_wait_idle_none_message_and_error(self):
        cases = (
            ([SessionIdleData()], None),
            ([AssistantMessageData(content="answer", message_id="m"), SessionIdleData()], "answer"),
            ([SessionErrorData(error_type="test", message="runtime failed")], RuntimeError),
        )
        for payloads, expected in cases:
            with self.subTest(expected=expected):
                session = CopilotSession("test", Mock())

                async def send(*_, **__):
                    for payload in payloads:
                        session._dispatch_event(event(payload))

                session.send = AsyncMock(side_effect=send)
                if expected is RuntimeError:
                    with self.assertRaisesRegex(Exception, "runtime failed"):
                        await session.send_and_wait("mock", timeout=1)
                else:
                    result = await session.send_and_wait("mock", timeout=1)
                    self.assertEqual(result.data.content if result else None, expected)
                self.assertFalse(session._event_handlers)

    async def test_real_disconnect_detaches_without_deleting(self):
        transport = SimpleNamespace(request=AsyncMock(return_value={"success": True}))
        session = CopilotSession("saved-id", transport)
        async with session:
            session.on(lambda _: None)
        await session.disconnect()  # Idempotent.
        transport.request.assert_awaited_once_with("session.detach", {"sessionId": "saved-id"})
        self.assertFalse(session._event_handlers)

    async def test_disconnect_cancels_in_flight_external_tool_task(self):
        transport = SimpleNamespace(request=AsyncMock(return_value={"success": True}))
        session = CopilotSession("test", transport)
        cancelled = asyncio.Event()

        async def external_tool():
            try:
                await asyncio.sleep(10)
            finally:
                cancelled.set()

        task = asyncio.create_task(external_tool())
        session._pending_external_tools["tool-request"] = task
        await asyncio.sleep(0)
        await session.disconnect()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(cancelled.is_set())

    def test_manifests_pin_stable_sdk_and_new_apis_exist(self):
        self.assertIn("github-copilot-sdk==1.0.13", (ROOT / "requirements.txt").read_text())
        config = tomllib.loads((ROOT / "pyproject.toml").read_text())
        self.assertIn("github-copilot-sdk==1.0.13", config["project"]["dependencies"])
        self.assertIn("client_info", inspect.signature(CopilotClient).parameters)
        for connection in (
            RuntimeConnection.for_stdio(path="vendor/copilot"),
            RuntimeConnection.for_uri("localhost:4321"),
        ):
            inspect.signature(CopilotClient).bind(connection=connection)
        for method in (CopilotClient.create_session, CopilotClient.resume_session):
            for option in ("ask_user_variant", "github_token_provider", "managed_settings"):
                self.assertIn(option, inspect.signature(method).parameters)
        self.assertTrue(hasattr(CopilotSession, "set_auto_tier"))
        self.assertIn("bearer_token_provider", ProviderConfig.__annotations__)
        self.assertIn("on_user_prompt_transformed", SessionHooks.__annotations__)
        self.assertIn("on_post_tool_use_failure", SessionHooks.__annotations__)


if __name__ == "__main__":
    unittest.main()
