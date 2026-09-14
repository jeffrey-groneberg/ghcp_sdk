"""Offline regression tests using real SDK types and a mocked runtime.

Run: python -m unittest discover -s examples/tests -v
No model call, authentication lookup, MCP request, sandboxed tool, or shell
command is executed.
"""

import asyncio
import ast
import contextlib
from html.parser import HTMLParser
import importlib.util
import inspect
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from copilot import CopilotClient, RuntimeConnection, ToolSet
from copilot.rpc import (
    AgentSelectRequest,
    PermissionDecisionApproveOnce,
    PermissionDecisionReject,
    PermissionDecisionUserNotAvailable,
    SandboxConfig,
    SessionUpdateOptionsParams,
)
from copilot.session import CopilotSession, ProviderConfig, SessionHooks
from copilot.session_events import (
    AssistantMessageData,
    AssistantMessageDeltaData,
    PermissionRequestRead,
    PermissionRequestShell,
    SessionErrorData,
    SessionIdleData,
    ToolExecutionCompleteData,
    ToolExecutionCompleteResult,
    ToolExecutionStartData,
)
from copilot.tools import ToolInvocation


ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = ROOT / "examples"
if str(EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLES_DIR))

import _console_input as console_input


EXAMPLE_FILES = sorted(EXAMPLES_DIR.glob("0[1-8]_*.py"))


def load_example(path: Path):
    spec = importlib.util.spec_from_file_location(f"example_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


EXAMPLES = [load_example(path) for path in EXAMPLE_FILES]
TEXT_ONLY = load_example(EXAMPLES_DIR / "text_only_chat.py")
FOUNDRY = load_example(EXAMPLES_DIR / "azure_foundry_byok.py")
FOUNDRY_ENV = {
    "FOUNDRY_MODEL_URL": "https://test-resource.openai.azure.com/openai/v1/",
    "FOUNDRY_API_KEY": "test-secret",
    "FOUNDRY_MODEL": "test-deployment",
}


class SlideCode(HTMLParser):
    def __init__(self):
        super().__init__()
        self.slide = 0
        self.in_code = False
        self.snippets = {}

    def handle_starttag(self, tag, attrs):
        if tag == "section":
            self.slide += 1
        if tag == "pre":
            self.in_code = True
            self.snippets.setdefault(self.slide, "")

    def handle_endtag(self, tag):
        if tag == "pre":
            self.in_code = False

    def handle_data(self, data):
        if self.in_code:
            self.snippets[self.slide] += data


def slide_code(number):
    parser = SlideCode()
    parser.feed((ROOT / "docs/index.html").read_text(encoding="utf-8"))
    return ast.parse(parser.snippets[number])


def slide_strings(number):
    return {
        node.value for node in ast.walk(slide_code(number))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


def event(data):
    return SimpleNamespace(type="test", data=data)


def final_reply():
    return event(AssistantMessageData(content="Mocked assistant response", message_id="message-1"))


def tool_names(value):
    return value.to_list() if isinstance(value, ToolSet) else value


class FakeSession:
    def __init__(self):
        self.session_id = "test-session"
        self.entered = self.exited = False
        self.listeners = []
        self.unsubscribed = 0
        self.send_and_wait = AsyncMock(return_value=final_reply())
        self.rpc = SimpleNamespace(
            agent=SimpleNamespace(
                list=AsyncMock(
                    return_value=SimpleNamespace(
                        agents=[
                            SimpleNamespace(name="researcher"),
                            SimpleNamespace(name="reviewer"),
                        ],
                    )
                ),
                get_current=AsyncMock(
                    side_effect=[
                        SimpleNamespace(agent=SimpleNamespace(name="researcher")),
                        SimpleNamespace(agent=SimpleNamespace(name="reviewer")),
                    ]
                ),
                select=AsyncMock(),
            ),
            options=SimpleNamespace(
                update=AsyncMock(return_value=SimpleNamespace(success=True)),
            ),
            tools=SimpleNamespace(
                initialize_and_validate=AsyncMock(),
                get_current_metadata=AsyncMock(
                    return_value=SimpleNamespace(
                        tools=[
                            SimpleNamespace(
                                name="ask_user",
                                input_schema={
                                    "properties": {
                                        "message": {},
                                        "requestedSchema": {},
                                    }
                                },
                            )
                        ]
                    )
                ),
            ),
        )

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
        self.session_options_history = []
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
        self.session_options_history.append(kwargs)
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
                stack.enter_context(
                    patch.object(module, "github_token", return_value="test-secret")
                )
                if (
                    client.session.send_and_wait.side_effect is None
                    and client.session.send_and_wait.return_value is not None
                ):
                    async def mcp_reply(*_, **__):
                        client.session.emit(
                            ToolExecutionStartData(
                                tool_call_id="tool-1",
                                tool_name="github-list_issues",
                                mcp_server_name="github",
                                mcp_tool_name="list_issues",
                                arguments={},
                            )
                        )
                        return final_reply()

                    client.session.send_and_wait.side_effect = mcp_reply
            stack.enter_context(contextlib.redirect_stdout(output))
            await module.main(*args)
        return output.getvalue()

    async def test_all_eight_use_valid_sdk_options_and_cleanup(self):
        self.assertEqual(len(EXAMPLES), 8)
        for module in EXAMPLES:
            with self.subTest(example=module.__name__):
                client = FakeClient()
                await self.run_example(module, client)
                self.assertTrue(client.entered and client.exited)
                self.assertTrue(client.session.entered and client.session.exited)
                self.assertIn("available_tools", client.session_options)
                self.assertIsInstance(client.session_options["available_tools"], (list, ToolSet))
                for call in client.session.send_and_wait.await_args_list:
                    self.assertGreater(call.kwargs["timeout"], 0)
                self.assertEqual(client.session.listeners, [])

    async def test_all_eight_propagate_timeout_error_and_cancellation(self):
        for module in EXAMPLES:
            for failure in (
                TimeoutError("deadline"),
                RuntimeError("runtime failed"),
                asyncio.CancelledError(),
            ):
                with self.subTest(example=module.__name__, failure=type(failure).__name__):
                    client = FakeClient()
                    client.session.send_and_wait.side_effect = failure
                    with self.assertRaises(type(failure)):
                        await self.run_example(module, client)
                    self.assertTrue(client.session.exited and client.exited)
                    self.assertEqual(client.session.listeners, [])

    async def test_all_eight_reject_missing_final_reply(self):
        for module in EXAMPLES:
            with self.subTest(example=module.__name__):
                client = FakeClient()
                client.session.send_and_wait.return_value = None
                with self.assertRaisesRegex(RuntimeError, "without an assistant message"):
                    await self.run_example(module, client)
                self.assertTrue(client.exited)

    async def test_streaming_and_client_identity(self):
        client = FakeClient()

        async def reply(*_, **__):
            client.session.emit(AssistantMessageDeltaData(delta_content="Hello", message_id="m"))
            client.session.emit(
                AssistantMessageDeltaData(delta_content=" world", message_id="m")
            )
            return final_reply()

        client.session.send_and_wait.side_effect = reply
        output = await self.run_example(EXAMPLES[0], client)
        self.assertEqual(output, "Hello world\n")
        self.assertEqual(client.session.unsubscribed, 1)
        self.assertEqual(tool_names(client.session_options["available_tools"]), [])
        self.assertNotIn("model", client.session_options)
        self.assertIn("GitHub Copilot SDK", client.session_options["system_message"]["content"])
        self.assertEqual(
            client.constructor_options["client_info"]["application_name"],
            "ghcp-sdk-examples",
        )
        self.assertEqual(
            client.constructor_options["client_info"]["integration_version"],
            "1.0.13",
        )

    async def test_agent_switch_uses_typed_request_and_checks_state(self):
        client = FakeClient()
        await self.run_example(EXAMPLES[2], client)
        selected = client.session.rpc.agent.select.await_args.args[0]
        self.assertIsInstance(selected, AgentSelectRequest)
        self.assertEqual(selected.name, "reviewer")
        self.assertEqual(client.session.send_and_wait.await_count, 2)
        self.assertEqual(EXAMPLES[2].AGENTS[0]["display_name"], "Research Agent")
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
                    {
                        "toolName": "view",
                        "toolArgs": "test-secret",
                        "toolResult": "test-secret",
                    },
                    {"session_id": "test"},
                )
                self.assertIsNone(result)
        self.assertIn("[pre]  view", output.getvalue())
        self.assertIn("[post] view done", output.getvalue())
        self.assertIn("[failed] view", output.getvalue())
        self.assertNotIn("test-secret", output.getvalue())
        client = FakeClient()
        await self.run_example(EXAMPLES[3], client)
        self.assertIn("on_post_tool_use_failure", client.session_options["hooks"])

    async def test_remote_github_mcp_uses_separate_auth_and_safe_trace(self):
        client = FakeClient()

        async def reply(*_, **__):
            client.session.emit(
                ToolExecutionStartData(
                    tool_call_id="tool-1",
                    tool_name="github-list_issues",
                    mcp_server_name="github",
                    mcp_tool_name="list_issues",
                    arguments={"private": "test-secret"},
                )
            )
            return final_reply()

        client.session.send_and_wait.side_effect = reply
        output = await self.run_example(EXAMPLES[4], client)
        server = client.session_options["mcp_servers"]["github"]
        self.assertEqual(
            server["tools"],
            ["list_issues", "issue_read", "search_issues"],
        )
        self.assertEqual(server["headers"]["X-MCP-Readonly"], "true")
        self.assertEqual(server["headers"]["Authorization"], "Bearer test-secret")
        self.assertEqual(
            tool_names(client.session_options["available_tools"]),
            [f"mcp:github-{name}" for name in server["tools"]],
        )
        self.assertIn("[mcp] github/list_issues", output)
        self.assertNotIn("test-secret", output)

    async def test_resume_resupplies_scope_without_repeating_facts(self):
        client = FakeClient()
        output = await self.run_example(EXAMPLES[5], client, True, "saved-conversation")
        self.assertEqual(client.resumed_id, "saved-conversation")
        self.assertNotIn("model", client.session_options)
        self.assertEqual(tool_names(client.session_options["available_tools"]), [])
        self.assertIn("on_permission_request", client.session_options)
        prompt = client.session.send_and_wait.await_args.args[0]
        self.assertNotIn("Jeffrey", prompt)
        self.assertNotIn("Python", prompt)
        self.assertIn("test-session", output)

    async def test_structured_input_variant_and_scoped_shell(self):
        client = FakeClient()
        await self.run_example(EXAMPLES[6], client)
        self.assertEqual(client.session_options["ask_user_variant"], "elicitation")
        self.assertIs(
            client.session_options["on_elicitation_request"],
            EXAMPLES[6].on_elicitation_request,
        )
        self.assertNotIn("on_user_input_request", client.session_options)
        self.assertEqual(
            tool_names(client.session_options["available_tools"]),
            ["builtin:ask_user", f"builtin:{EXAMPLES[6].SHELL_TOOL}"],
        )

    async def test_human_input_falls_back_when_structured_tool_is_unavailable(self):
        client = FakeClient()
        client.session.rpc.tools.get_current_metadata.return_value = SimpleNamespace(
            tools=[
                SimpleNamespace(
                    name="ask_user",
                    input_schema={"properties": {"question": {}}},
                ),
                SimpleNamespace(
                    name=EXAMPLES[6].SHELL_TOOL,
                    input_schema={},
                ),
            ]
        )
        output = await self.run_example(EXAMPLES[6], client)
        self.assertEqual(
            [options["ask_user_variant"] for options in client.session_options_history],
            ["elicitation", "legacy"],
        )
        self.assertIs(
            client.session_options["on_user_input_request"],
            EXAMPLES[6].on_user_input_request,
        )
        self.assertIn("falling back", output)

    async def test_sandbox_uses_official_config_shape_and_feature_flag(self):
        client = FakeClient()
        await self.run_example(EXAMPLES[7], client)
        self.assertIn(
            "SANDBOX",
            client.constructor_options["env"]["COPILOT_CLI_ENABLED_FEATURE_FLAGS"],
        )
        self.assertEqual(
            tool_names(client.session_options["available_tools"]),
            ["builtin:grep"],
        )
        update = client.session.rpc.options.update.await_args.args[0]
        self.assertIsInstance(update, SessionUpdateOptionsParams)
        config = update.sandbox_config
        self.assertIsInstance(config, SandboxConfig)
        self.assertTrue(config.enabled)
        self.assertTrue(config.allow_bypass)
        self.assertTrue(config.add_current_working_directory)
        workspace = Path(client.session_options["working_directory"])
        self.assertEqual(
            config.user_policy.filesystem.denied_paths,
            [str(workspace / "vault")],
        )
        self.assertFalse(config.user_policy.network.allow_local_network)
        self.assertFalse(config.user_policy.network.allow_outbound)
        prompt = client.session.send_and_wait.await_args.args[0]
        self.assertIn("the host verifies that independently", prompt)
        self.assertNotIn("reply exactly SANDBOX_BYPASS_APPROVED", prompt)

    async def test_runtime_prompts_match_the_restored_html_slides(self):
        for module, number in (
            (TEXT_ONLY, 5), (EXAMPLES[0], 18), (EXAMPLES[1], 19),
            (EXAMPLES[2], 20), (EXAMPLES[3], 21), (EXAMPLES[4], 22),
        ):
            with self.subTest(slide=number):
                client = FakeClient()
                await self.run_example(module, client)
                for call in client.session.send_and_wait.await_args_list:
                    self.assertIn(call.args[0], slide_strings(number))
        client = FakeClient()
        await self.run_example(EXAMPLES[5], client)
        self.assertIn(client.session.send_and_wait.await_args.args[0], slide_strings(23))
        client = FakeClient()
        await self.run_example(EXAMPLES[5], client, True)
        self.assertIn(client.session.send_and_wait.await_args.args[0], slide_strings(23))

    async def test_agent_definitions_and_relative_file_match_slide_20(self):
        assignment = next(
            node for node in slide_code(20).body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "AGENTS" for target in node.targets)
        )
        shown_agents = ast.literal_eval(assignment.value)
        for shown, actual in zip(shown_agents, EXAMPLES[2].AGENTS, strict=True):
            for key in ("name", "display_name", "tools", "prompt"):
                self.assertEqual(actual[key], shown[key])
        client = FakeClient()
        await self.run_example(EXAMPLES[2], client)
        folder = Path(client.session_options["working_directory"])
        self.assertEqual(folder, EXAMPLES_DIR)
        self.assertTrue((folder / "01_simple_chat.py").is_file())

    async def test_additional_slide_examples_use_real_sdk_configuration(self):
        for module, number in ((TEXT_ONLY, 5), (FOUNDRY, 15)):
            with self.subTest(slide=number), patch.dict(FOUNDRY.os.environ, FOUNDRY_ENV, clear=True):
                client = FakeClient()
                output = await self.run_example(module, client)
                self.assertIn(client.session.send_and_wait.await_args.args[0], slide_strings(number))
                self.assertEqual(client.session_options["available_tools"], [])
                self.assertTrue(client.exited and client.session.exited)
                self.assertIn("Mocked assistant response", output)
                self.assertNotIn("test-secret", output)
                if module is TEXT_ONLY:
                    self.assertNotIn("streaming", client.session_options)
                    self.assertNotIn("model", client.session_options)
                    self.assertIn("GitHub Copilot SDK", client.session_options["system_message"]["content"])
                else:
                    self.assertEqual(client.session_options["provider"], {
                        "type": "openai",
                        "base_url": FOUNDRY_ENV["FOUNDRY_MODEL_URL"],
                        "api_key": FOUNDRY_ENV["FOUNDRY_API_KEY"],
                        "wire_api": "responses",
                    })
                    self.assertEqual(client.session_options["model"], FOUNDRY_ENV["FOUNDRY_MODEL"])

    async def test_additional_slide_examples_propagate_failures_and_cleanup(self):
        for module in (TEXT_ONLY, FOUNDRY):
            for failure in (None, TimeoutError("deadline"), RuntimeError("session error"),
                            asyncio.CancelledError()):
                with (
                    self.subTest(example=module.__name__, failure=type(failure).__name__),
                    patch.dict(FOUNDRY.os.environ, FOUNDRY_ENV, clear=True),
                ):
                    client = FakeClient()
                    client.session.send_and_wait.return_value = None
                    client.session.send_and_wait.side_effect = failure
                    with self.assertRaises(type(failure) if failure is not None else RuntimeError):
                        await self.run_example(module, client)
                    self.assertTrue(client.exited and client.session.exited)

    async def test_foundry_missing_configuration_fails_before_client_start(self):
        for name in FOUNDRY_ENV:
            for value in (None, "", "   "):
                env = dict(FOUNDRY_ENV)
                if value is None:
                    del env[name]
                else:
                    env[name] = value
                with (
                    self.subTest(name=name, value=value),
                    patch.dict(FOUNDRY.os.environ, env, clear=True),
                    patch.object(FOUNDRY, "CopilotClient") as client,
                    self.assertRaisesRegex(ValueError, name),
                ):
                    await FOUNDRY.main()
                client.assert_not_called()

    def test_foundry_rejects_wrong_endpoint_without_exposing_credentials(self):
        for url in (
            "http://test-resource.openai.azure.com/openai/v1/",
            "https://test-resource.openai.azure.com/",
            "https://user:test-secret@test-resource.openai.azure.com/openai/v1/",
            "https://test-resource.openai.azure.com/openai/v1/?key=test-secret",
            "https://test-resource.openai.azure.com/openai/v1/#test-secret",
        ):
            with patch.dict(FOUNDRY.os.environ, {**FOUNDRY_ENV, "FOUNDRY_MODEL_URL": url}, clear=True):
                with self.assertRaises(ValueError) as failure:
                    FOUNDRY.load_configuration()
                self.assertIn("FOUNDRY_MODEL_URL", str(failure.exception))
                self.assertNotIn("test-secret", str(failure.exception))


class ToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_weather_schema_and_fictional_results(self):
        tool = EXAMPLES[1].get_weather
        self.assertEqual(tool.parameters["required"], ["city"])
        self.assertEqual(tool.parameters["properties"]["city"]["minLength"], 1)
        with patch.object(EXAMPLES[1].random, "randint", return_value=21):
            result = await tool.handler(ToolInvocation(arguments={"city": "Tokyo"}))
        self.assertEqual(result.result_type, "success")
        data = json.loads(result.text_result_for_llm)
        self.assertEqual((data["city"], data["temperature_c"]), ("Tokyo", 21))
        self.assertEqual(data["source"], "fictional demo")
        self.assertEqual(data["condition"], "sunny")
        self.assertIn(data["source"], slide_strings(19))
        self.assertIn(data["condition"], slide_strings(19))
        self.assertIn(tool.description, slide_strings(19))

    async def test_weather_schema_rejects_empty_city(self):
        result = await EXAMPLES[1].get_weather.handler(
            ToolInvocation(arguments={"city": ""})
        )
        self.assertEqual(result.result_type, "failure")


class TokenTests(unittest.TestCase):
    def test_import_never_resolves_credentials_or_starts_client(self):
        with patch("subprocess.check_output") as lookup, patch.object(
            CopilotClient, "start"
        ) as start:
            for path in EXAMPLE_FILES:
                load_example(path)
        lookup.assert_not_called()
        start.assert_not_called()

    def test_environment_precedence_and_gh_fallback(self):
        with (
            patch.dict(
                "os.environ",
                {"GITHUB_TOKEN": " first ", "GH_TOKEN": "second"},
                clear=True,
            ),
            patch("subprocess.check_output") as lookup,
        ):
            self.assertEqual(EXAMPLES[4].github_token(), "first")
            lookup.assert_not_called()

        with (
            patch.dict("os.environ", {}, clear=True),
            patch("subprocess.check_output", return_value=" token \n") as lookup,
        ):
            self.assertEqual(EXAMPLES[4].github_token(), "token")
        self.assertEqual(
            lookup.call_args.args[0],
            ["gh", "auth", "token", "--hostname", "github.com"],
        )
        self.assertEqual(lookup.call_args.kwargs["timeout"], 10)
        self.assertIs(lookup.call_args.kwargs["stderr"], subprocess.DEVNULL)

    def test_token_failures_are_clear_without_secret_output(self):
        failures = (
            FileNotFoundError(),
            subprocess.CalledProcessError(1, "gh", output="private-token"),
            subprocess.TimeoutExpired("gh", 10, output="private-token"),
        )
        for failure in failures:
            with (
                self.subTest(failure=type(failure).__name__),
                patch.dict("os.environ", {}, clear=True),
                patch("subprocess.check_output", side_effect=failure),
            ):
                with self.assertRaises(RuntimeError) as raised:
                    EXAMPLES[4].github_token()
                self.assertNotIn("private-token", str(raised.exception))
                self.assertTrue(raised.exception.__suppress_context__)


class HumanInputTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.module = EXAMPLES[6]
        console_input.reset_input_state()

    def shell_request(self, command=None, **kwargs):
        return PermissionRequestShell(
            can_offer_session_approval=False,
            commands=[],
            full_command_text=command or self.module.EXPECTED_COMMAND,
            has_write_file_redirection=False,
            intention="greet",
            possible_paths=[],
            possible_urls=[],
            **kwargs,
        )

    def elicitation_context(self):
        return {
            "session_id": "test",
            "message": "What is your name?",
            "mode": "form",
            "requestedSchema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "title": "Name",
                    }
                },
                "required": ["name"],
            },
        }

    async def test_expected_name_form_accepts_valid_input(self):
        with (
            patch.object(self.module, "read_answer", AsyncMock(return_value="Ada")),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            result = await self.module.on_elicitation_request(self.elicitation_context())
        self.assertEqual(result, {"action": "accept", "content": {"name": "Ada"}})

    async def test_unexpected_or_url_elicitation_is_declined(self):
        cases = (
            {"session_id": "test", "message": "Open", "mode": "url", "url": "https://example.com"},
            {
                "session_id": "test",
                "message": "Secret",
                "requestedSchema": {
                    "type": "object",
                    "properties": {"token": {"type": "string"}},
                    "required": ["token"],
                },
            },
        )
        for context in cases:
            with (
                self.subTest(context=context["message"]),
                patch.object(self.module, "read_answer") as reader,
                contextlib.redirect_stderr(io.StringIO()),
            ):
                self.assertEqual(
                    await self.module.on_elicitation_request(context),
                    {"action": "decline"},
                )
                reader.assert_not_called()

    async def test_name_validation_retries_then_cancels(self):
        with (
            patch.object(
                self.module,
                "read_answer",
                AsyncMock(side_effect=["", "x" * 81, "Ada"]),
            ) as reader,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            result = await self.module.on_elicitation_request(self.elicitation_context())
        self.assertEqual(result["content"]["name"], "Ada")
        self.assertEqual(reader.await_count, 3)

        with (
            patch.object(self.module, "read_answer", AsyncMock(side_effect=TimeoutError)),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(
                await self.module.on_elicitation_request(self.elicitation_context()),
                {"action": "cancel"},
            )

    async def test_legacy_fallback_accepts_only_one_freeform_name(self):
        with (
            patch.object(self.module, "read_answer", AsyncMock(return_value="Ada")),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            result = await self.module.on_user_input_request(
                {
                    "question": "What is your name?",
                    "allowFreeform": True,
                },
                {},
            )
        self.assertEqual(result, {"answer": "Ada", "wasFreeform": True})

        with self.assertRaisesRegex(ValueError, "freeform name"):
            await self.module.on_user_input_request(
                {
                    "question": "Choose",
                    "choices": ["Ada"],
                    "allowFreeform": False,
                },
                {},
            )

    async def test_permission_approval_denial_and_unavailable_input(self):
        for answer, expected in (
            ("y", PermissionDecisionApproveOnce),
            ("N", PermissionDecisionReject),
            ("", PermissionDecisionReject),
        ):
            with (
                self.subTest(answer=answer),
                patch.object(self.module, "read_answer", AsyncMock(return_value=answer)),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                result = await self.module.on_permission_request(self.shell_request(), {})
                self.assertIsInstance(result, expected)

        for failure in (TimeoutError(), EOFError(), OSError()):
            with (
                patch.object(self.module, "read_answer", AsyncMock(side_effect=failure)),
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                result = await self.module.on_permission_request(self.shell_request(), {})
                self.assertIsInstance(result, PermissionDecisionUserNotAvailable)

    async def test_permission_rejects_unexpected_actions_without_prompting(self):
        requests = (
            self.shell_request(command="echo unexpected"),
            self.shell_request(request_sandbox_bypass=True),
            PermissionRequestRead(intention="read", path="private-file"),
        )
        for request in requests:
            with (
                self.subTest(request=type(request).__name__),
                patch.object(self.module, "read_answer") as reader,
                contextlib.redirect_stdout(io.StringIO()),
            ):
                result = await self.module.on_permission_request(request, {})
                self.assertIsInstance(result, PermissionDecisionReject)
                reader.assert_not_called()

    async def test_managed_permission_still_requires_explicit_human_input(self):
        with (
            patch.object(self.module, "read_answer", AsyncMock(return_value="y")) as reader,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            result = await self.module.on_permission_request(
                self.shell_request(managed_approval_required=True),
                {},
            )
        self.assertIsInstance(result, PermissionDecisionApproveOnce)
        reader.assert_awaited_once()

    async def test_callbacks_propagate_cancellation(self):
        for callback, request in (
            (self.module.on_elicitation_request, self.elicitation_context()),
            (
                self.module.on_user_input_request,
                {"question": "What is your name?", "allowFreeform": True},
            ),
            (self.module.on_permission_request, self.shell_request()),
        ):
            with (
                patch.object(
                    self.module,
                    "read_answer",
                    AsyncMock(side_effect=asyncio.CancelledError),
                ),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                with self.assertRaises(asyncio.CancelledError):
                    if callback is self.module.on_permission_request:
                        await callback(request, {})
                    elif callback is self.module.on_user_input_request:
                        await callback(request, {})
                    else:
                        await callback(request)


class SandboxTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.module = EXAMPLES[7]
        console_input.reset_input_state()

    async def test_bypass_requires_one_explicit_human_decision(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = Path(temp_dir) / "vault"
            vault.mkdir()
            state = self.module.ApprovalState()
            handler = self.module.permission_handler(vault, state)
            request = PermissionRequestRead(
                intention="search",
                path=str(vault / "notes.txt"),
                request_sandbox_bypass=True,
                request_sandbox_bypass_reason="The sandbox denied the path.",
            )
            with (
                patch.object(self.module, "read_answer", AsyncMock(return_value="y")) as reader,
                contextlib.redirect_stdout(io.StringIO()),
            ):
                result = await handler(request, {})
                repeated = await handler(request, {})
            self.assertIsInstance(result, PermissionDecisionApproveOnce)
            self.assertIsInstance(repeated, PermissionDecisionReject)
            self.assertTrue(state.bypass_requested)
            self.assertTrue(state.bypass_approved)
            reader.assert_awaited_once()

    async def test_managed_or_out_of_scope_reads_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = Path(temp_dir) / "vault"
            vault.mkdir()
            handler = self.module.permission_handler(
                vault,
                self.module.ApprovalState(),
            )
            managed = PermissionRequestRead(
                intention="search",
                path=str(vault),
                managed_approval_required=True,
            )
            outside = PermissionRequestRead(
                intention="search",
                path=str(Path(temp_dir) / "outside"),
            )
            self.assertIsInstance(
                await handler(managed, {}),
                PermissionDecisionUserNotAvailable,
            )
            self.assertIsInstance(
                await handler(outside, {}),
                PermissionDecisionReject,
            )

    def test_bypass_evidence_uses_matching_tool_result(self):
        state = self.module.ApprovalState(bypass_approved=True)
        started = ToolExecutionStartData(
            tool_call_id="grep-1",
            tool_name="grep",
        )
        completed = ToolExecutionCompleteData(
            success=True,
            tool_call_id="grep-1",
            result=ToolExecutionCompleteResult(
                content=f"/tmp/vault/notes.txt:{self.module.MARKER}",
            ),
            sandboxed=True,
        )

        self.assertEqual(
            self.module.record_grep_evidence(started, state),
            "[tool] grep started",
        )
        self.assertEqual(
            self.module.record_grep_evidence(completed, state),
            "[tool] completed success=True sandboxed=True",
        )
        self.assertTrue(state.grep_succeeded)
        self.assertTrue(state.marker_found)
        self.assertTrue(self.module.bypass_verified(state))

    def test_bypass_evidence_accepts_success_when_result_omits_marker(self):
        state = self.module.ApprovalState(
            bypass_requested=True,
            bypass_approved=True,
            grep_tool_call_id="grep-1",
        )
        completed = ToolExecutionCompleteData(
            success=True,
            tool_call_id="grep-1",
            result=ToolExecutionCompleteResult(content="Search completed."),
            sandboxed=True,
        )

        self.module.record_grep_evidence(completed, state)

        self.assertTrue(state.grep_succeeded)
        self.assertFalse(state.marker_found)
        self.assertTrue(self.module.bypass_verified(state))

    def test_runtime_env_preserves_existing_feature_flags(self):
        with patch.dict(
            self.module.os.environ,
            {"COPILOT_CLI_ENABLED_FEATURE_FLAGS": "EXTENSIONS"},
            clear=True,
        ):
            env = self.module.sandbox_runtime_env()
        self.assertEqual(
            set(env["COPILOT_CLI_ENABLED_FEATURE_FLAGS"].split(",")),
            {"EXTENSIONS", "SANDBOX"},
        )


class ConsoleInputTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        console_input.reset_input_state()

    async def test_console_reader_success_eof_and_timeout(self):
        with patch("builtins.input", return_value=" Ada "):
            self.assertEqual(
                await console_input.read_answer("Name: ", timeout=1),
                "Ada",
            )

        console_input.reset_input_state()
        with patch("builtins.input", side_effect=EOFError):
            with self.assertRaises(EOFError):
                await console_input.read_answer("Name: ", timeout=1)
        with self.assertRaises(EOFError):
            await console_input.read_answer("Do not start another reader: ", timeout=1)

        console_input.reset_input_state()
        with patch.object(console_input.threading, "Thread") as thread:
            with self.assertRaises(TimeoutError):
                await console_input.read_answer("Name: ", timeout=0.001)
            self.assertTrue(thread.call_args.kwargs["daemon"])
            with self.assertRaises(EOFError):
                await console_input.read_answer("Do not start another reader: ", timeout=1)
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
            (
                [
                    AssistantMessageData(content="answer", message_id="m"),
                    SessionIdleData(),
                ],
                "answer",
            ),
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
        await session.disconnect()
        transport.request.assert_awaited_once_with(
            "session.detach",
            {"sessionId": "saved-id"},
        )
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

    def test_manifests_pin_stable_sdk_and_current_apis_exist(self):
        self.assertIn(
            "github-copilot-sdk==1.0.13",
            (ROOT / "requirements.txt").read_text(),
        )
        config = tomllib.loads((ROOT / "pyproject.toml").read_text())
        self.assertIn(
            "github-copilot-sdk==1.0.13",
            config["project"]["dependencies"],
        )
        self.assertIn("client_info", inspect.signature(CopilotClient).parameters)
        self.assertIn("mode", inspect.signature(CopilotClient).parameters)
        for connection in (
            RuntimeConnection.for_stdio(path="vendor/copilot"),
            RuntimeConnection.for_uri("localhost:4321"),
        ):
            inspect.signature(CopilotClient).bind(connection=connection)
        for method in (CopilotClient.create_session, CopilotClient.resume_session):
            for option in (
                "ask_user_variant",
                "github_token_provider",
                "managed_settings",
                "on_elicitation_request",
            ):
                self.assertIn(option, inspect.signature(method).parameters)
        self.assertTrue(hasattr(CopilotSession, "set_auto_tier"))
        self.assertIn("bearer_token_provider", ProviderConfig.__annotations__)
        self.assertIn("on_user_prompt_transformed", SessionHooks.__annotations__)
        self.assertIn("on_post_tool_use_failure", SessionHooks.__annotations__)
        self.assertEqual(
            ToolSet().add_builtin(["grep", "view"]).to_list(),
            ["builtin:grep", "builtin:view"],
        )
        self.assertEqual(
            SandboxConfig(enabled=True, allow_bypass=True).to_dict(),
            {"enabled": True, "allowBypass": True},
        )


if __name__ == "__main__":
    unittest.main()
