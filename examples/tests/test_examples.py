"""Offline contracts with real SDK 1.0.13 types and a mocked runtime.

Run: python -m unittest discover -s examples/tests -v
No model, MCP server, sandbox backend, authentication lookup or shell command
is called. Disposable filesystem fixtures stay under examples/ and are removed.
"""

import asyncio
import ast
import contextlib
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
    AgentGetCurrentResult,
    AgentInfo,
    AgentList,
    AgentSelectRequest,
    CurrentToolMetadata,
    PermissionDecisionApproveOnce,
    PermissionDecisionReject,
    PermissionDecisionUserNotAvailable,
    SandboxConfig,
    SessionUpdateOptionsParams,
    SessionUpdateOptionsResult,
    ToolsGetCurrentMetadataResult,
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
    ToolExecutionCompleteError,
    ToolExecutionCompleteResult,
    ToolExecutionStartData,
)
from copilot.tools import ToolInvocation
from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = ROOT / "examples"
if str(EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLES_DIR))

import _console_input as console_input
from _tool_trace import ToolTrace


EXAMPLE_FILES = sorted(EXAMPLES_DIR.glob("0[1-8]_*.py"))


def load_example(path: Path):
    spec = importlib.util.spec_from_file_location(f"example_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


EXAMPLES = [load_example(path) for path in EXAMPLE_FILES]


def event(data):
    return SimpleNamespace(type="test", data=data)


def final_reply():
    return event(AssistantMessageData(content="Mocked assistant commentary", message_id="message-1"))


def tool_names(value):
    return value.to_list() if isinstance(value, ToolSet) else value


def completed(call_id, content="result", *, success=True):
    return ToolExecutionCompleteData(
        tool_call_id=call_id,
        success=success,
        result=ToolExecutionCompleteResult(content=content) if content is not None else None,
        error=None if success else ToolExecutionCompleteError(message="Mocked tool failure"),
        sandboxed=True,
    )


def shell_request(command=None, **kwargs):
    return PermissionRequestShell(
        can_offer_session_approval=False,
        commands=[],
        full_command_text=EXAMPLES[6].EXPECTED_COMMAND if command is None else command,
        has_write_file_redirection=False,
        intention="Run workshop unit tests",
        possible_paths=[],
        possible_urls=[],
        tool_call_id=kwargs.pop("tool_call_id", "command-1"),
        **kwargs,
    )


def shell_args():
    return {
        "command": EXAMPLES[6].EXPECTED_COMMAND,
        "description": "Run the workshop offline tests",
        "mode": "sync",
        "initial_wait": 120,
    }


def hook_input(name, arguments, directory):
    return {
        "sessionId": "test-session",
        "toolName": name,
        "toolArgs": arguments,
        "workingDirectory": str(directory),
    }


def metadata_tool(name, properties):
    return CurrentToolMetadata(
        name=name,
        description="Offline metadata fixture",
        input_schema={"type": "object", "properties": properties},
    )


def metadata():
    return ToolsGetCurrentMetadataResult(tools=[
        metadata_tool("ask_user", {"message": {}, "requestedSchema": {}}),
        metadata_tool("grep", {
            "pattern": {"type": "string"},
            "paths": {"type": "string"},
            "glob": {"type": "string"},
            "-n": {"type": "boolean"},
            "head_limit": {"type": "number"},
            "output_mode": {"type": "string", "enum": ["content", "files_with_matches", "count"]},
        }),
    ])


def agent_info(name):
    return AgentInfo(name=name, id=name, display_name=name.title(), description="Offline agent fixture")


class FakeSession:
    def __init__(self):
        self.session_id = "test-session"
        self.entered = self.exited = False
        self.listeners = []
        self.unsubscribed = 0
        self.send_and_wait = AsyncMock(return_value=final_reply())
        self.rpc = SimpleNamespace(
            agent=SimpleNamespace(
                list=AsyncMock(return_value=AgentList(agents=[
                    agent_info("researcher"), agent_info("reviewer"),
                ])),
                get_current=AsyncMock(side_effect=[
                    AgentGetCurrentResult(agent=agent_info("researcher")),
                    AgentGetCurrentResult(agent=agent_info("reviewer")),
                ]),
                select=AsyncMock(),
            ),
            options=SimpleNamespace(
                update=AsyncMock(return_value=SessionUpdateOptionsResult(success=True)),
            ),
            tools=SimpleNamespace(
                initialize_and_validate=AsyncMock(),
                get_current_metadata=AsyncMock(return_value=metadata()),
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


async def simulate_tool_use(module, client):
    """Drive real callbacks with fabricated runtime events; NOT live evidence."""
    session, options = client.session, client.session_options
    if module is EXAMPLES[1]:
        result = await module.inspect_python_file.handler(
            ToolInvocation(tool_call_id="inspect-1", arguments={"file": module.REVIEW_FILE})
        )
        if result.result_type != "success":
            raise AssertionError(result.error)
    elif module is EXAMPLES[3]:
        arguments = {"path": str(module.REVIEW_PATH)}
        data = hook_input("view", arguments, module.REPO_ROOT)
        await options["hooks"]["on_pre_tool_use"](data, {})
        session.emit(ToolExecutionStartData(
            tool_name="view", tool_call_id="view-1", arguments=arguments,
        ))
        session.emit(completed("view-1", "1: Example 01 source (offline fixture)"))
        await options["hooks"]["on_post_tool_use"]({**data, "toolResult": "source"}, {})
    elif module is EXAMPLES[4]:
        session.emit(ToolExecutionStartData(
            tool_call_id="mcp-1", tool_name="github-list_issues",
            mcp_server_name="github", mcp_tool_name="list_issues",
            arguments={"owner": module.TARGET_REPO_OWNER, "repo": module.TARGET_REPO_NAME},
        ))
        session.emit(completed("mcp-1", "[]"))
    elif module is EXAMPLES[6]:
        if options["ask_user_variant"] == "elicitation":
            result = await options["on_elicitation_request"]({
                "session_id": "test-session", "message": "Choose a review focus",
                "requestedSchema": module.FOCUS_SCHEMA,
            })
            if result["action"] != "accept":
                raise AssertionError(result)
        else:
            await options["on_user_input_request"]({
                "question": "Choose a review focus", "allowFreeform": True,
            }, {})
        arguments = shell_args()
        decision = await options["hooks"]["on_pre_tool_use"](
            hook_input(module.SHELL_TOOL, arguments, module.REPO_ROOT), {},
        )
        if decision is not None:
            raise AssertionError(decision)
        session.emit(ToolExecutionStartData(
            tool_name=module.SHELL_TOOL, tool_call_id="command-1", arguments=arguments,
        ))
        approved = await options["on_permission_request"](shell_request(), {})
        success = isinstance(approved, PermissionDecisionApproveOnce)
        session.emit(completed(
            "command-1", "Ran 4 tests in 0.010s\n\nOK\n" if success else None, success=success,
        ))
    elif module is EXAMPLES[7]:
        vault = Path(options["working_directory"]) / "vault"
        note = (vault / module.NOTE_FILENAME).read_text().strip()
        arguments = module.ApprovalState(vault=vault, note_content=note).grep_arguments
        decision = await options["hooks"]["on_pre_tool_use"](
            hook_input("grep", arguments, vault.parent), {},
        )
        if decision is not None:
            raise AssertionError(decision)
        session.emit(ToolExecutionStartData(
            tool_name="grep", tool_call_id="grep-1", arguments=arguments,
        ))
        approved = await options["on_permission_request"](PermissionRequestRead(
            intention="Search the disposable note", path=str(vault),
            request_sandbox_bypass=True, tool_call_id="grep-1",
            request_sandbox_bypass_reason="Offline fixture: denied path",
        ), {})
        success = isinstance(approved, PermissionDecisionApproveOnce)
        session.emit(completed(
            "grep-1", f"{vault / module.NOTE_FILENAME}:1:{note}" if success else None,
            success=success,
        ))


class PrototypeTests(unittest.IsolatedAsyncioTestCase):
    async def run_example(self, module, client, *args, approval="y"):
        output = io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(module, "CopilotClient", client.factory))
            if hasattr(module, "github_token"):
                stack.enter_context(patch.object(module, "github_token", return_value="offline-token"))
            if hasattr(module, "read_answer"):
                stack.enter_context(patch.object(module, "read_answer", AsyncMock(
                    side_effect=lambda prompt, **_: "errors" if prompt.startswith("Review focus") else approval,
                )))
            stack.enter_context(contextlib.redirect_stdout(output))
            stack.enter_context(contextlib.redirect_stderr(output))
            if (
                client.session.send_and_wait.side_effect is None
                and client.session.send_and_wait.return_value is not None
            ):
                async def reply(*_, **__):
                    await simulate_tool_use(module, client)
                    return final_reply()
                client.session.send_and_wait.side_effect = reply
            try:
                await module.main(*args)
            finally:
                self.last_output = output.getvalue()
        return output.getvalue()

    async def test_eight_independent_samples_valid_options_default_model_and_cleanup(self):
        self.assertEqual(len(EXAMPLES), 8)
        for module in EXAMPLES:
            with self.subTest(example=module.__name__):
                client = FakeClient()
                await self.run_example(module, client)
                self.assertTrue(client.entered and client.exited)
                self.assertTrue(client.session.entered and client.session.exited)
                self.assertIsInstance(client.session_options["available_tools"], (list, ToolSet))
                self.assertNotIn("model", client.session_options)
                for call in client.session.send_and_wait.await_args_list:
                    self.assertGreater(call.kwargs["timeout"], 0)
                self.assertEqual(client.session.listeners, [])

    async def test_all_samples_propagate_timeout_error_and_cancellation(self):
        for module in EXAMPLES:
            for failure in (TimeoutError("deadline"), RuntimeError("runtime failed"), asyncio.CancelledError()):
                with self.subTest(example=module.__name__, failure=type(failure).__name__):
                    client = FakeClient()
                    client.session.send_and_wait.side_effect = failure
                    with self.assertRaises(type(failure)):
                        await self.run_example(module, client)
                    self.assertTrue(client.session.exited and client.exited)
                    self.assertEqual(client.session.listeners, [])

    async def test_all_samples_require_a_final_message(self):
        for module in EXAMPLES:
            with self.subTest(example=module.__name__):
                client = FakeClient()
                client.session.send_and_wait.return_value = None
                with self.assertRaisesRegex(RuntimeError, "without an assistant message"):
                    await self.run_example(module, client)
                self.assertTrue(client.exited and client.session.exited)
                self.assertEqual(client.session.listeners, [])

    async def test_streaming_plan_uses_supplied_description_not_file_tools(self):
        client = FakeClient()

        async def reply(*_, **__):
            for delta in ("Check errors", " and cleanup"):
                client.session.emit(AssistantMessageDeltaData(delta_content=delta, message_id="m"))
            return final_reply()

        client.session.send_and_wait.side_effect = reply
        output = await self.run_example(EXAMPLES[0], client)
        self.assertEqual(output, "Check errors and cleanup\n")
        self.assertEqual(client.session.unsubscribed, 1)
        self.assertEqual(tool_names(client.session_options["available_tools"]), [])
        prompt = client.session.send_and_wait.await_args.args[0]
        self.assertIn(EXAMPLES[0].REPOSITORY_DESCRIPTION, prompt)
        self.assertIn("do not claim to have read", prompt)
        self.assertEqual(client.constructor_options["client_info"]["integration_version"], "1.0.13")

    async def test_streaming_prints_final_content_when_no_deltas_arrive(self):
        output = await self.run_example(EXAMPLES[0], FakeClient())
        self.assertEqual(output, "Mocked assistant commentary\n")

    async def test_custom_tool_handler_must_really_run_for_the_target(self):
        client = FakeClient()
        client.session.send_and_wait.side_effect = lambda *_, **__: final_reply()
        with self.assertRaisesRegex(RuntimeError, "No successful inspect_python_file"):
            await self.run_example(EXAMPLES[1], client)
        self.assertEqual(EXAMPLES[1].INSPECTIONS, [])

    async def test_agents_share_the_review_file_and_verify_both_personas(self):
        client = FakeClient()
        await self.run_example(EXAMPLES[2], client)
        selected = client.session.rpc.agent.select.await_args.args[0]
        self.assertIsInstance(selected, AgentSelectRequest)
        self.assertEqual(selected.name, "reviewer")
        self.assertEqual(client.session_options["working_directory"], str(ROOT))
        for call in client.session.send_and_wait.await_args_list:
            self.assertIn(EXAMPLES[2].REVIEW_FILE, call.args[0])
        self.assertEqual(tool_names(client.session_options["available_tools"]),
                         ["builtin:grep", "builtin:glob", "builtin:view"])
        for phase in ("researcher", "reviewer"):
            for wrong in (None, agent_info("wrong-agent")):
                with self.subTest(phase=phase, wrong=wrong):
                    client = FakeClient()
                    client.session.rpc.agent.get_current.side_effect = (
                        [AgentGetCurrentResult(agent=wrong)] if phase == "researcher" else
                        [AgentGetCurrentResult(agent=agent_info("researcher")), AgentGetCurrentResult(agent=wrong)]
                    )
                    with self.assertRaisesRegex(RuntimeError, f"{phase} persona"):
                        await self.run_example(EXAMPLES[2], client)
                    self.assertEqual(client.session.send_and_wait.await_count, 0 if phase == "researcher" else 1)

    async def test_hooks_log_without_enforcement_or_payload_logging(self):
        module = EXAMPLES[3]
        output = io.StringIO()
        data = {
            "toolName": "view", "toolArgs": "private-payload",
            "toolResult": "private-payload", "error": "file missing",
        }
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            for name in ("on_pre_tool_use", "on_post_tool_use", "on_post_tool_use_failure"):
                self.assertIsNone(await getattr(module, name)(data, {}))
        self.assertIn("[pre]  view", output.getvalue())
        self.assertIn("[post] view succeeded", output.getvalue())
        self.assertIn("[failed] view: file missing", output.getvalue())
        self.assertNotIn("private-payload", output.getvalue())

    async def test_hooks_require_a_matching_successful_file_read(self):
        module = EXAMPLES[3]
        for failure in ("not-called", "wrong-path", "wrong-id", "failed", "empty", "no-result"):
            with self.subTest(failure=failure):
                client = FakeClient()

                async def reply(*_, **__):
                    if failure != "not-called":
                        client.session.emit(ToolExecutionStartData(
                            tool_call_id="view-1", tool_name="view",
                            arguments={"path": str(module.REVIEW_PATH) if failure != "wrong-path" else str(ROOT)},
                        ))
                        content = None if failure == "no-result" else "" if failure == "empty" else "source"
                        client.session.emit(completed(
                            "other" if failure == "wrong-id" else "view-1",
                            content, success=failure != "failed",
                        ))
                    return final_reply()

                client.session.send_and_wait.side_effect = reply
                with self.assertRaisesRegex(RuntimeError, "No matching successful view result"):
                    await self.run_example(module, client)

    async def test_mcp_uses_supplied_bearer_token_and_safe_correlated_logs(self):
        module, client = EXAMPLES[4], FakeClient()
        output = await self.run_example(module, client)
        server = client.session_options["mcp_servers"]["github"]
        self.assertEqual(server["headers"]["Authorization"], "Bearer " + "offline-token")
        self.assertEqual(server["headers"]["X-MCP-Readonly"], "true")
        self.assertEqual(server["tools"], ["list_issues"])
        self.assertEqual(tool_names(client.session_options["available_tools"]), ["mcp:github-list_issues"])
        self.assertNotIn("offline-token", output)
        self.assertNotIn("Authorization", output)
        self.assertIn("[mcp] github/list_issues started id=mcp-1", output)
        self.assertIn("[mcp] github/list_issues completed id=mcp-1 success=True", output)
        self.assertIn("[host] MCP_ISSUES_VERIFIED repo=jeffrey-groneberg/ghcp_sdk", output)
        self.assertNotIn("github_token", client.constructor_options)

    async def test_mcp_requires_target_start_success_result_and_matching_id(self):
        module = EXAMPLES[4]
        for failure in ("not-called", "wrong-server", "wrong-tool", "wrong-repo", "no-start",
                        "wrong-id", "failed", "no-result", "not-completed"):
            with self.subTest(failure=failure):
                client = FakeClient()

                async def reply(*_, **__):
                    if failure == "not-called":
                        return final_reply()
                    if failure != "no-start":
                        client.session.emit(ToolExecutionStartData(
                            tool_call_id="mcp-1", tool_name="github-list_issues",
                            mcp_server_name="other" if failure == "wrong-server" else "github",
                            mcp_tool_name="write_issue" if failure == "wrong-tool" else "list_issues",
                            arguments={"owner": module.TARGET_REPO_OWNER,
                                       "repo": "other" if failure == "wrong-repo" else module.TARGET_REPO_NAME},
                        ))
                    if failure != "not-completed":
                        client.session.emit(completed(
                            "other" if failure == "wrong-id" else "mcp-1",
                            None if failure == "no-result" else "[]", success=failure != "failed",
                        ))
                    return final_reply()

                client.session.send_and_wait.side_effect = reply
                with self.assertRaisesRegex(RuntimeError, "No complete successful GitHub issue query"):
                    await self.run_example(module, client)

    async def test_cold_resume_reinstates_policy_without_supplying_the_facts(self):
        module = EXAMPLES[5]
        first = FakeClient()
        await self.run_example(module, first, False, "workshop-review-1")
        prompt = first.session.send_and_wait.await_args.args[0]
        self.assertIn(module.REVIEW_FILE, prompt)
        self.assertIn(module.REVIEW_FOCUS, prompt)
        resumed = FakeClient()
        await self.run_example(module, resumed, True, "workshop-review-1")
        self.assertEqual(resumed.resumed_id, "workshop-review-1")
        self.assertEqual(tool_names(resumed.session_options["available_tools"]), [])
        self.assertIn("on_permission_request", resumed.session_options)
        prompt = resumed.session.send_and_wait.await_args.args[0]
        self.assertNotIn(module.REVIEW_FILE, prompt)
        self.assertNotIn(module.REVIEW_FOCUS, prompt)

    async def test_structured_focus_and_command_have_host_verified_results(self):
        client = FakeClient()
        output = await self.run_example(EXAMPLES[6], client)
        self.assertEqual(client.session_options["ask_user_variant"], "elicitation")
        self.assertIn("on_elicitation_request", client.session_options)
        self.assertNotIn("on_user_input_request", client.session_options)
        self.assertEqual(client.session_options["working_directory"], str(ROOT))
        self.assertIn("[hitl] focus accepted: errors", output)
        self.assertIn("[host] COMMAND_APPROVE_ONCE id=command-1", output)
        self.assertIn("[host] COMMAND_RESULT_VERIFIED id=command-1; unittest reported OK", output)

    async def test_legacy_fallback_is_explicit_and_validates_the_same_focus(self):
        client = FakeClient()
        client.session.rpc.tools.get_current_metadata.return_value = ToolsGetCurrentMetadataResult(
            tools=[metadata_tool("ask_user", {"question": {}})],
        )
        output = await self.run_example(EXAMPLES[6], client)
        self.assertEqual([opts["ask_user_variant"] for opts in client.session_options_history],
                         ["elicitation", "legacy"])
        self.assertIn("on_user_input_request", client.session_options)
        self.assertIn("falling back to the legacy question contract", output)
        self.assertIn("[hitl] focus accepted: errors", output)

    async def test_hitl_denial_has_a_host_trace_not_a_fake_success(self):
        output = await self.run_example(EXAMPLES[6], FakeClient(), approval="n")
        self.assertIn("[host] COMMAND_DENIED id=command-1 reason=user rejected", output)
        self.assertIn("[host] COMMAND_DENIAL_RECORDED id=command-1; no execution claimed", output)
        self.assertNotIn("COMMAND_RESULT_VERIFIED", output)

    async def test_sandbox_uses_content_scope_nonce_and_experimental_typed_config(self):
        module, client = EXAMPLES[7], FakeClient()
        output = await self.run_example(module, client)
        config_request = client.session.rpc.options.update.await_args.args[0]
        self.assertIsInstance(config_request, SessionUpdateOptionsParams)
        config = config_request.sandbox_config
        self.assertIsInstance(config, SandboxConfig)
        self.assertTrue(config.enabled and config.allow_bypass and config.add_current_working_directory)
        workspace = Path(client.session_options["working_directory"])
        self.assertTrue(workspace.is_relative_to(EXAMPLES_DIR))
        self.assertFalse(workspace.exists(), "Disposable vault must be removed even after success.")
        self.assertEqual(config.user_policy.filesystem.denied_paths, [str(workspace / "vault")])
        self.assertFalse(config.user_policy.network.allow_local_network)
        self.assertFalse(config.user_policy.network.allow_outbound)
        self.assertIn("SANDBOX", client.constructor_options["env"]["COPILOT_CLI_ENABLED_FEATURE_FLAGS"])
        self.assertEqual(tool_names(client.session_options["available_tools"]), ["builtin:grep"])
        prompt = client.session.send_and_wait.await_args.args[0]
        self.assertIn('"output_mode": "content"', prompt)
        self.assertIn('"glob": "review-note.txt"', prompt)
        self.assertNotIn("nonce=", prompt)
        self.assertIn("[host] SANDBOX_BYPASS_APPROVE_ONCE id=grep-1", output)
        self.assertIn("[host] SANDBOX_BYPASS_VERIFIED id=grep-1; matching result contains the private note", output)

    async def test_sandbox_denial_is_host_evidence_not_a_claim_of_containment(self):
        output = await self.run_example(EXAMPLES[7], FakeClient(), approval="n")
        self.assertIn("[host] SANDBOX_BYPASS_DENIED id=grep-1 reason=user rejected", output)
        self.assertIn("[host] SANDBOX_DENIAL_RECORDED id=grep-1; no access claimed", output)
        self.assertNotIn("SANDBOX_BYPASS_VERIFIED", output)

    async def test_no_model_prose_can_substitute_for_hitl_or_sandbox_evidence(self):
        for module in (EXAMPLES[6], EXAMPLES[7]):
            client = FakeClient()
            client.session.send_and_wait.side_effect = lambda *_, **__: event(
                AssistantMessageData(content="Approved and verified! All tests pass; note found.", message_id="m"),
            )
            with self.subTest(module=module.__name__), self.assertRaises(RuntimeError):
                await self.run_example(module, client)

    async def test_sandbox_missing_metadata_or_rejected_config_fails_before_model_call(self):
        for failure in ("no-grep", "no-content", "bad-properties", "config-rejected"):
            with self.subTest(failure=failure):
                client = FakeClient()
                if failure == "no-grep":
                    client.session.rpc.tools.get_current_metadata.return_value = ToolsGetCurrentMetadataResult()
                elif failure in ("no-content", "bad-properties"):
                    info = metadata()
                    tool = info.tools[1]
                    if failure == "no-content":
                        tool.input_schema["properties"]["output_mode"]["enum"] = ["files_with_matches"]
                    else:
                        tool.input_schema["properties"] = None
                    client.session.rpc.tools.get_current_metadata.return_value = info
                else:
                    client.session.rpc.options.update.return_value = SessionUpdateOptionsResult(success=False)
                with self.assertRaises(RuntimeError):
                    await self.run_example(EXAMPLES[7], client)
                client.session.send_and_wait.assert_not_awaited()
                self.assertFalse(Path(client.session_options["working_directory"]).exists())

    async def test_missing_backend_is_visible_incomplete_and_cleans_up(self):
        client = FakeClient()

        async def reply(*_, **__):
            client.session.emit(ToolExecutionStartData(tool_name="grep", tool_call_id="grep-1"))
            client.session.emit(ToolExecutionCompleteData(
                tool_call_id="grep-1", success=False,
                error=ToolExecutionCompleteError(message="Sandbox backend unavailable"),
            ))
            return final_reply()

        client.session.send_and_wait.side_effect = reply
        with self.assertRaisesRegex(RuntimeError, "tool/backend support is incomplete"):
            await self.run_example(EXAMPLES[7], client)
        self.assertIn("[tool] failed: Sandbox backend unavailable", self.last_output)
        self.assertIn(
            "[host] SANDBOX_INCOMPLETE reason=No host sandbox-bypass decision; "
            "tool/backend support is incomplete.",
            self.last_output,
        )
        self.assertNotIn("SANDBOX_BYPASS_VERIFIED", self.last_output)
        self.assertFalse(Path(client.session_options["working_directory"]).exists())


class CustomToolTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.module = EXAMPLES[1]
        self.module.INSPECTIONS.clear()

    async def invoke(self, arguments):
        with contextlib.redirect_stdout(io.StringIO()):
            return await self.module.inspect_python_file.handler(ToolInvocation(arguments=arguments))

    def test_typed_tool_excerpt_stays_short_and_matches_walkthrough(self):
        source = Path(self.module.__file__).read_text()
        definitions = {
            node.name: node for node in ast.parse(source).body
            if isinstance(node, (ast.ClassDef, ast.AsyncFunctionDef))
        }
        start = definitions["FileParams"].lineno
        end = definitions["inspect_python_file"].end_lineno
        self.assertLessEqual(end - start + 1, 14)
        excerpt = "\n".join(source.splitlines()[start - 1:end])
        walkthrough = (EXAMPLES_DIR / "02_custom_tools.md").read_text()
        self.assertIn(f"```python\n{excerpt}\n```", walkthrough)

    async def test_typed_handler_delegates_only_validated_parameters(self):
        with patch.object(self.module, "read_python_metadata",
                          wraps=self.module.read_python_metadata) as helper:
            result = await self.invoke({"file": self.module.REVIEW_FILE})
            self.assertEqual(result.result_type, "success")
            helper.assert_called_once()
            self.assertIsInstance(helper.call_args.args[0], self.module.FileParams)
            self.assertEqual(helper.call_args.args[0].file, self.module.REVIEW_FILE)
            helper.reset_mock()
            rejected = await self.invoke({"file": "../README.md"})
            self.assertEqual(rejected.result_type, "failure")
            helper.assert_not_called()

    async def test_typed_schema_and_deterministic_ast_metadata(self):
        tool = self.module.inspect_python_file
        self.assertEqual(tool.name, "inspect_python_file")
        self.assertEqual(tool.parameters["required"], ["file"])
        self.assertFalse(tool.parameters["additionalProperties"])
        self.assertEqual(tool.parameters["properties"]["file"]["enum"],
                         ["examples/01_simple_chat.py", "examples/02_custom_tools.py"])
        first = await self.invoke({"file": self.module.REVIEW_FILE})
        second = await self.invoke({"file": self.module.REVIEW_FILE})
        self.assertEqual(first.result_type, "success")
        self.assertEqual(first.text_result_for_llm, second.text_result_for_llm)
        data = json.loads(first.text_result_for_llm)
        source = (ROOT / self.module.REVIEW_FILE).read_text()
        self.assertEqual(data["line_count"], len(source.splitlines()))
        self.assertEqual(data["file"], self.module.REVIEW_FILE)
        self.assertIn("asyncio", data["imports"])
        self.assertIn("main", data["functions"])
        self.assertIn("on_event", data["functions"])
        self.assertEqual(self.module.INSPECTIONS, [data, data])

    async def test_parameters_reject_traversal_absolute_paths_wrong_types_and_extras(self):
        for arguments in (
            {}, {"file": ""}, {"file": "../README.md"},
            {"file": "examples/../examples/01_simple_chat.py"},
            {"file": str(ROOT / self.module.REVIEW_FILE)},
            {"file": "examples/03_custom_agents.py"}, {"file": "*.py"},
            {"file": 1}, {"file": None}, {"file": ["examples/01_simple_chat.py"]},
            {"file": self.module.REVIEW_FILE, "command": "something"},
        ):
            with self.subTest(arguments=arguments):
                with self.assertRaises(ValidationError):
                    self.module.FileParams.model_validate(arguments)
                result = await self.invoke(arguments)
                self.assertEqual(result.result_type, "failure")
                self.assertIn("Invalid tool arguments", result.text_result_for_llm)
        self.assertEqual(self.module.INSPECTIONS, [])

    async def test_reads_are_bounded_and_symlinks_missing_files_and_bad_python_fail(self):
        with tempfile.TemporaryDirectory(prefix="sdk-test-", dir="examples") as directory:
            root = Path(directory).resolve()
            (root / "examples").mkdir()
            selected = root / self.module.REVIEW_FILE
            with patch.object(self.module, "REPO_ROOT", root):
                missing = await self.invoke({"file": self.module.REVIEW_FILE})
                self.assertEqual(missing.result_type, "failure")
                for raw, error in (
                    (b"x" * (self.module.MAX_FILE_BYTES + 1), "read limit"),
                    (b"def broken(:", "invalid syntax"),
                    (b"\xff", "utf-8"),
                ):
                    selected.write_bytes(raw)
                    result = await self.invoke({"file": self.module.REVIEW_FILE})
                    self.assertEqual(result.result_type, "failure")
                    self.assertIn(error, result.error)
                selected.unlink()
                outside = root / "not-allowlisted.py"
                outside.write_text("import os\n")
                selected.symlink_to(outside)
                result = await self.invoke({"file": self.module.REVIEW_FILE})
                self.assertEqual(result.result_type, "failure")
                self.assertIn("Symlinked sample paths", result.error)
        self.assertEqual(self.module.INSPECTIONS, [])


class TokenTests(unittest.TestCase):
    def test_import_has_no_credentials_or_client_side_effects(self):
        with patch("subprocess.check_output") as lookup, patch.object(CopilotClient, "start") as start:
            for path in EXAMPLE_FILES:
                load_example(path)
        lookup.assert_not_called()
        start.assert_not_called()

    def test_header_uses_the_supplied_token_without_logging_it(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            first = EXAMPLES[4].build_mcp_servers("first-fixture-token")
            second = EXAMPLES[4].build_mcp_servers("second-fixture-token")
        self.assertEqual(first["github"]["headers"]["Authorization"], "Bearer " + "first-fixture-token")
        self.assertEqual(second["github"]["headers"]["Authorization"], "Bearer " + "second-fixture-token")
        self.assertEqual(output.getvalue(), "")

    def test_environment_precedence_and_gh_fallback(self):
        with patch.dict("os.environ", {"GITHUB_TOKEN": " first ", "GH_TOKEN": "second"}, clear=True), \
                patch("subprocess.check_output") as lookup:
            self.assertEqual(EXAMPLES[4].github_token(), "first")
            lookup.assert_not_called()
        with patch.dict("os.environ", {"GH_TOKEN": " second "}, clear=True):
            self.assertEqual(EXAMPLES[4].github_token(), "second")
        with patch.dict("os.environ", {}, clear=True), \
                patch("subprocess.check_output", return_value=" token \n") as lookup:
            self.assertEqual(EXAMPLES[4].github_token(), "token")
        self.assertEqual(lookup.call_args.args[0], ["gh", "auth", "token", "--hostname", "github.com"])
        self.assertEqual(lookup.call_args.kwargs["timeout"], 10)
        self.assertIs(lookup.call_args.kwargs["stderr"], subprocess.DEVNULL)

    def test_token_failures_do_not_expose_credential_diagnostics(self):
        for failure in (FileNotFoundError(), subprocess.CalledProcessError(1, "gh", output="private-token"),
                        subprocess.TimeoutExpired("gh", 10, output="private-token")):
            with self.subTest(failure=type(failure).__name__), \
                    patch.dict("os.environ", {}, clear=True), \
                    patch("subprocess.check_output", side_effect=failure):
                with self.assertRaises(RuntimeError) as raised:
                    EXAMPLES[4].github_token()
                self.assertNotIn("private-token", str(raised.exception))
                self.assertTrue(raised.exception.__suppress_context__)
        with patch.dict("os.environ", {}, clear=True), patch("subprocess.check_output", return_value=""):
            with self.assertRaisesRegex(RuntimeError, "empty token"):
                EXAMPLES[4].github_token()


class HumanInputTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.module = EXAMPLES[6]
        console_input.reset_input_state()

    def context(self):
        return {"session_id": "test", "message": "Choose focus", "mode": "form",
                "requestedSchema": self.module.FOCUS_SCHEMA}

    def host_with_result(self, *, decision="approve-once", content="Ran 2 tests in 0.1s\n\nOK\n", success=True):
        host = self.module.ReviewHost(focus="errors", decision=decision, decision_call_id="command-1")
        host.trace.record(ToolExecutionStartData(
            tool_name=self.module.SHELL_TOOL, tool_call_id="command-1", arguments=shell_args(),
        ))
        host.trace.record(completed("command-1", content, success=success))
        return host

    def test_focus_values_are_validated_not_interpolated(self):
        for value, expected in (("errors", "errors"), (" cleanup ", "cleanup"), ("ERRORS", "errors")):
            self.assertEqual(self.module.validate_focus(value), expected)
        for value in ("", "error handling", "errors; whoami", "cleanup\nanything", "x" * 1000, None, []):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.module.validate_focus(value)

    async def test_structured_focus_retries_with_validated_content(self):
        host = self.module.ReviewHost()
        with patch.object(self.module, "read_answer", AsyncMock(side_effect=["", "arbitrary", " cleanup "])) as reader, \
                contextlib.redirect_stdout(io.StringIO()):
            result = await host.on_elicitation_request(self.context())
        self.assertEqual(result, {"action": "accept", "content": {"focus": "cleanup"}})
        self.assertEqual(host.focus, "cleanup")
        self.assertEqual(reader.await_count, 3)

    async def test_unexpected_form_or_url_requests_decline_without_prompting(self):
        invalid = [
            {**self.context(), "mode": "url"},
            {**self.context(), "requestedSchema": None},
            {**self.context(), "requestedSchema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
        ]
        for field in ({"type": "number"}, {"type": "string", "enum": ["secrets"]}, {"type": "string", "pattern": ".+"}):
            invalid.append({**self.context(), "requestedSchema": {
                "type": "object", "properties": {"focus": field}, "required": ["focus"],
            }})
        for context in invalid:
            with self.subTest(context=context), patch.object(self.module, "read_answer") as reader, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(await self.module.ReviewHost().on_elicitation_request(context), {"action": "decline"})
                reader.assert_not_called()

    async def test_focus_input_failure_cancels_structured_and_fails_legacy(self):
        for failure in (TimeoutError(), EOFError(), OSError()):
            with self.subTest(failure=type(failure).__name__), \
                    patch.object(self.module, "read_answer", AsyncMock(side_effect=failure)), \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(await self.module.ReviewHost().on_elicitation_request(self.context()), {"action": "cancel"})
                with self.assertRaisesRegex(RuntimeError, "input unavailable"):
                    await self.module.ReviewHost().on_user_input_request({"allowFreeform": True}, {})
        with patch.object(self.module, "read_answer", AsyncMock(return_value="wrong")), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(await self.module.ReviewHost().on_elicitation_request(self.context()), {"action": "cancel"})

    async def test_legacy_fallback_validates_focus_and_rejects_other_contracts(self):
        host = self.module.ReviewHost()
        with patch.object(self.module, "read_answer", AsyncMock(return_value="errors")), \
                contextlib.redirect_stdout(io.StringIO()):
            result = await host.on_user_input_request({"question": "Focus?", "allowFreeform": True}, {})
        self.assertEqual(result, {"answer": "errors", "wasFreeform": True})
        for request in ({"choices": ["errors"]}, {"allowFreeform": False}):
            with self.assertRaisesRegex(ValueError, "freeform review focus"):
                await self.module.ReviewHost().on_user_input_request(request, {})
        with self.assertRaisesRegex(ValueError, "Only one"):
            await host.collect_focus()

    def test_shell_validation_rejects_metacharacters_and_nonliteral_commands(self):
        command = self.module.EXPECTED_COMMAND
        self.assertTrue(self.module.is_expected_command(command))
        for value in (
            command + "; whoami", command + " && whoami", command + " | cat",
            command + " > file", command + " < file", command + "\n", command + "\r",
            command + " # comment", command + " $(whoami)", command + " `whoami`",
            command + " ${HOME}", command + "\\\n", " " + command, command + " ",
            command.replace("python", "python3", 1), command.replace("python", "'python'", 1),
        ):
            with self.subTest(command=value):
                self.assertFalse(self.module.is_expected_command(value))
        for extra in ({"shellId": "old-session"}, {"mode": "async"}, {"detach": True},
                      {"cwd": str(ROOT)}, {"initial_wait": 30}):
            self.assertFalse(self.module.is_safe_shell_args({**shell_args(), **extra}))

    async def test_pre_hook_requires_fresh_scoped_shell_and_defers_to_permission(self):
        host = self.module.ReviewHost(focus="errors")
        good = hook_input(self.module.SHELL_TOOL, shell_args(), ROOT)
        self.assertIsNone(await host.on_pre_tool_use(good, {}))
        for bad in (
            {**good, "workingDirectory": str(ROOT.parent)},
            {**good, "toolArgs": {**shell_args(), "shellId": "old"}},
            {**good, "toolName": "view"},
        ):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual((await host.on_pre_tool_use(bad, {}))["permissionDecision"], "deny")

    async def test_permission_approve_once_denial_unavailable_and_no_second_decision(self):
        for answer, expected, text in (
            ("y", PermissionDecisionApproveOnce, "COMMAND_APPROVE_ONCE"),
            ("N", PermissionDecisionReject, "COMMAND_DENIED"),
            ("", PermissionDecisionReject, "COMMAND_DENIED"),
        ):
            host = self.module.ReviewHost(focus="errors")
            output = io.StringIO()
            with patch.object(self.module, "read_answer", AsyncMock(return_value=answer)) as reader, \
                    contextlib.redirect_stdout(output):
                result = await host.on_permission_request(shell_request(), {})
                repeated = await host.on_permission_request(shell_request(tool_call_id="command-2"), {})
            self.assertIsInstance(result, expected)
            self.assertIsInstance(repeated, PermissionDecisionReject)
            self.assertIn(text, output.getvalue())
            self.assertEqual(host.decision_call_id, "command-1")
            reader.assert_awaited_once()
        for failure in (TimeoutError(), EOFError(), OSError()):
            with patch.object(self.module, "read_answer", AsyncMock(side_effect=failure)), \
                    contextlib.redirect_stdout(io.StringIO()):
                result = await self.module.ReviewHost(focus="cleanup").on_permission_request(shell_request(), {})
                self.assertIsInstance(result, PermissionDecisionUserNotAvailable)

    async def test_out_of_scope_missing_id_or_bypass_permissions_are_never_prompted(self):
        requests = (
            shell_request(command="echo unexpected"),
            shell_request(request_sandbox_bypass=True),
            shell_request(tool_call_id=None),
            PermissionRequestRead(intention="read", path="private-file", tool_call_id="read-1"),
        )
        for request in requests:
            with patch.object(self.module, "read_answer") as reader, contextlib.redirect_stdout(io.StringIO()):
                result = await self.module.ReviewHost(focus="errors").on_permission_request(request, {})
                self.assertIsInstance(result, PermissionDecisionReject)
                reader.assert_not_called()
        with patch.object(self.module, "read_answer") as reader, contextlib.redirect_stdout(io.StringIO()):
            self.assertIsInstance(await self.module.ReviewHost().on_permission_request(shell_request(), {}),
                                  PermissionDecisionReject)
            reader.assert_not_called()

    async def test_managed_permission_still_needs_human_input(self):
        with patch.object(self.module, "read_answer", AsyncMock(return_value="y")) as reader, \
                contextlib.redirect_stdout(io.StringIO()):
            result = await self.module.ReviewHost(focus="errors").on_permission_request(
                shell_request(managed_approval_required=True), {},
            )
        self.assertIsInstance(result, PermissionDecisionApproveOnce)
        reader.assert_awaited_once()

    def test_command_verification_rejects_unapproved_failed_missing_or_wrong_id_results(self):
        cases = [
            self.host_with_result(decision="reject"),
            self.host_with_result(content=None),
            self.host_with_result(content="The model says tests passed."),
            self.host_with_result(content="Ran 0 tests in 0s\n\nOK"),
            self.host_with_result(content="Ran 4 tests in 0.1s\n\nFAILED (failures=1)"),
            self.host_with_result(content="Ran 2 tests in 0.1s\n\nOK\nRan 4 tests in 0.2s\n\nFAILED (errors=1)"),
            self.host_with_result(success=False),
        ]
        mismatch = self.host_with_result()
        mismatch.decision_call_id = "other"
        cases.append(mismatch)
        missing_start = self.host_with_result()
        missing_start.trace.started.clear()
        cases.append(missing_start)
        for host in cases:
            with self.subTest(host=host), contextlib.redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError):
                host.report_outcome()

    def test_unittest_summary_requires_a_real_nonzero_final_passing_summary(self):
        self.assertTrue(self.module.unittest_reported_ok("Ran 2 tests in 0.1s\n\nOK (skipped=1)\n"))
        self.assertTrue(self.module.unittest_reported_ok("Ran 1 test in 0.1s\r\n\r\nOK\r\n"))
        self.assertFalse(self.module.unittest_reported_ok("Ran 2 tests in 0.1s\nOK"))
        self.assertFalse(self.module.unittest_reported_ok("Ran 2 tests in 0.1s\n\nFAILED\nOK"))

    async def test_callbacks_propagate_cancellation(self):
        for callback in ("on_elicitation_request", "on_user_input_request", "on_permission_request"):
            host = self.module.ReviewHost()
            with patch.object(self.module, "read_answer", AsyncMock(side_effect=asyncio.CancelledError)), \
                    contextlib.redirect_stdout(io.StringIO()), self.assertRaises(asyncio.CancelledError):
                if callback == "on_elicitation_request":
                    await host.on_elicitation_request(self.context())
                elif callback == "on_user_input_request":
                    await host.on_user_input_request({"allowFreeform": True}, {})
                else:
                    host.focus = "errors"
                    await host.on_permission_request(shell_request(), {})


class SandboxTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.module = EXAMPLES[7]
        self.directory = tempfile.TemporaryDirectory(prefix="sdk-test-", dir="examples")
        self.addCleanup(self.directory.cleanup)
        vault = Path(self.directory.name) / "vault"
        vault.mkdir()
        self.vault = vault.resolve()
        self.note = self.module.make_review_note()
        (vault / self.module.NOTE_FILENAME).write_text(self.note + "\n")

    def state(self):
        return self.module.ApprovalState(vault=self.vault, note_content=self.note)

    def request(self, **kwargs):
        return PermissionRequestRead(
            intention="Search disposable note",
            path=kwargs.pop("path", str(self.vault)),
            tool_call_id=kwargs.pop("tool_call_id", "grep-1"),
            request_sandbox_bypass=kwargs.pop("request_sandbox_bypass", True),
            **kwargs,
        )

    def recorded_state(self):
        state = self.state()
        state.hook_accepted = state.bypass_requested = True
        state.bypass_decision, state.bypass_call_id = "approve-once", "grep-1"
        self.module.record_grep_evidence(ToolExecutionStartData(
            tool_name="grep", tool_call_id="grep-1", arguments=state.grep_arguments,
        ), state)
        self.module.record_grep_evidence(completed("grep-1", self.note), state)
        return state

    def test_note_nonce_is_generated_and_not_the_search_pattern(self):
        other = self.module.make_review_note()
        self.assertNotEqual(other, self.note)
        self.assertRegex(self.note, r"nonce=[0-9a-f]{32}$")
        self.assertNotIn(self.note.split("nonce=")[1], json.dumps(self.state().grep_arguments))
        self.assertEqual(self.state().grep_arguments["output_mode"], "content")
        self.assertEqual(self.state().grep_arguments["glob"], "review-note.txt")
        self.assertIn("examples/01_simple_chat.py", self.note)

    async def test_one_exact_content_grep_is_enforced_without_inventing_hook_ids(self):
        state = self.state()
        hook = self.module.scoped_grep_hook(state)
        request = hook_input("grep", state.grep_arguments, self.vault.parent)
        self.assertIsNone(await hook(request, {}))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual((await hook(request, {}))["permissionDecision"], "deny")
        for arguments in (
            {**state.grep_arguments, "paths": str(self.vault.parent)},
            {**state.grep_arguments, "pattern": ".*"},
            {**state.grep_arguments, "output_mode": "files_with_matches"},
            {**state.grep_arguments, "glob": "*"},
            {**state.grep_arguments, "-A": 10},
        ):
            state = self.state()
            with contextlib.redirect_stdout(io.StringIO()):
                result = await self.module.scoped_grep_hook(state)(
                    hook_input("grep", arguments, self.vault.parent), {},
                )
            self.assertEqual(result["permissionDecision"], "deny")
            self.assertFalse(state.hook_accepted)
        self.assertNotIn("toolCallId", inspect.get_annotations(
            __import__("copilot.session", fromlist=["PreToolUseHookInput"]).PreToolUseHookInput,
        ))

    async def test_permission_uses_real_request_id_and_one_human_decision(self):
        state = self.state()
        handler = self.module.permission_handler(state)
        output = io.StringIO()
        with patch.object(self.module, "read_answer", AsyncMock(return_value="y")) as reader, \
                contextlib.redirect_stdout(output):
            result = await handler(self.request(tool_call_id="actual-permission-id"), {})
            repeated = await handler(self.request(tool_call_id="different-id"), {})
        self.assertIsInstance(result, PermissionDecisionApproveOnce)
        self.assertIsInstance(repeated, PermissionDecisionReject)
        self.assertEqual(state.bypass_call_id, "actual-permission-id")
        self.assertEqual(state.bypass_decision, "approve-once")
        self.assertIn("SANDBOX_BYPASS_APPROVE_ONCE id=actual-permission-id", output.getvalue())
        reader.assert_awaited_once()

    async def test_denial_timeout_eof_and_cancellation_do_not_approve(self):
        for answer in ("n", ""):
            state = self.state()
            with patch.object(self.module, "read_answer", AsyncMock(return_value=answer)), \
                    contextlib.redirect_stdout(io.StringIO()):
                result = await self.module.permission_handler(state)(self.request(), {})
            self.assertIsInstance(result, PermissionDecisionReject)
            self.assertEqual(state.bypass_decision, "reject")
        for failure in (EOFError(), OSError(), TimeoutError()):
            state = self.state()
            with patch.object(self.module, "read_answer", AsyncMock(side_effect=failure)), \
                    contextlib.redirect_stdout(io.StringIO()):
                result = await self.module.permission_handler(state)(self.request(), {})
            self.assertIsInstance(result, PermissionDecisionUserNotAvailable)
            self.assertEqual(state.bypass_decision, "unavailable")
        state = self.state()
        with patch.object(self.module, "read_answer", AsyncMock(side_effect=asyncio.CancelledError)), \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaises(asyncio.CancelledError):
            await self.module.permission_handler(state)(self.request(), {})
        self.assertIsNone(state.bypass_decision)

    async def test_only_vault_or_note_paths_and_correlated_reads_are_in_scope(self):
        outside = Path(self.directory.name) / "outside.txt"
        outside.write_text("not in the vault")
        requests = (
            self.request(path=str(outside.resolve())),
            self.request(path="vault"),
            self.request(path=str(self.vault / "missing.txt")),
            self.request(tool_call_id=None),
            shell_request(),
        )
        for request in requests:
            with patch.object(self.module, "read_answer") as reader, contextlib.redirect_stdout(io.StringIO()):
                self.assertIsInstance(await self.module.permission_handler(self.state())(request, {}),
                                      PermissionDecisionReject)
                reader.assert_not_called()

    async def test_ordinary_read_approval_is_not_bypass_and_managed_read_fails_closed(self):
        state = self.state()
        with patch.object(self.module, "read_answer") as reader, contextlib.redirect_stdout(io.StringIO()):
            handler = self.module.permission_handler(state)
            self.assertIsInstance(await handler(self.request(request_sandbox_bypass=False), {}),
                                  PermissionDecisionApproveOnce)
            self.assertIsInstance(await handler(self.request(
                request_sandbox_bypass=False, managed_approval_required=True,
            ), {}), PermissionDecisionUserNotAvailable)
            reader.assert_not_called()
        self.assertFalse(state.bypass_requested)
        self.assertFalse(self.module.bypass_verified(state))

    def test_approved_matching_content_verifies_independent_of_sandboxed_telemetry(self):
        for sandboxed in (True, False, None):
            state = self.recorded_state()
            state.trace.completed["grep-1"].sandboxed = sandboxed
            self.assertTrue(self.module.bypass_verified(state))
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.module.report_outcome(state)
            self.assertIn("SANDBOX_BYPASS_VERIFIED", output.getvalue())

    def test_no_marker_filenames_query_echo_or_generic_success_can_verify(self):
        for content in ("", "Search completed.", str(self.vault / self.module.NOTE_FILENAME),
                        self.module.SEARCH_PATTERN, self.note.split("nonce=")[0], "No matches found.", None):
            with self.subTest(content=content):
                state = self.recorded_state()
                state.trace.completed["grep-1"] = completed("grep-1", content)
                self.assertFalse(self.module.bypass_verified(state))
                with self.assertRaisesRegex(RuntimeError, "lacks a matching successful result"):
                    self.module.report_outcome(state)

    def test_an_empty_expected_note_cannot_verify_any_result(self):
        state = self.recorded_state()
        state.note_content = ""
        self.assertFalse(self.module.bypass_verified(state))
        with self.assertRaises(RuntimeError):
            self.module.report_outcome(state)

    def test_wrong_ids_failed_results_unapproved_access_and_wrong_scope_never_verify(self):
        for failure in ("wrong-approval-id", "wrong-result-id", "failed", "no-result", "no-completion",
                        "no-start", "wrong-tool", "wrong-path", "unapproved", "no-bypass-request", "no-hook"):
            with self.subTest(failure=failure):
                state = self.recorded_state()
                if failure == "wrong-approval-id":
                    state.bypass_call_id = "different"
                elif failure == "wrong-result-id":
                    state.trace.completed.clear()
                    state.trace.record(completed("different", self.note))
                elif failure == "failed":
                    state.trace.completed["grep-1"].success = False
                elif failure == "no-result":
                    state.trace.completed["grep-1"].result = None
                elif failure == "no-completion":
                    state.trace.completed.clear()
                elif failure == "no-start":
                    state.trace.started.clear()
                elif failure == "wrong-tool":
                    state.trace.started["grep-1"].tool_name = "view"
                elif failure == "wrong-path":
                    state.trace.started["grep-1"].arguments["paths"] = str(self.vault.parent)
                elif failure == "unapproved":
                    state.bypass_decision = "reject"
                elif failure == "no-bypass-request":
                    state.bypass_requested = False
                else:
                    state.hook_accepted = False
                self.assertFalse(self.module.bypass_verified(state))
                with self.assertRaises(RuntimeError):
                    self.module.report_outcome(state)

    def test_denial_records_no_access_and_missing_completion_is_incomplete(self):
        state = self.recorded_state()
        state.bypass_decision = "reject"
        state.trace.completed["grep-1"] = completed("grep-1", None, success=False)
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.module.report_outcome(state)
        self.assertIn("SANDBOX_DENIAL_RECORDED", output.getvalue())
        self.assertNotIn("VERIFIED", output.getvalue())
        state.trace.completed.clear()
        with self.assertRaisesRegex(RuntimeError, "Missing matching"):
            self.module.report_outcome(state)

    def test_runtime_environment_preserves_flags_and_does_not_disable_controls(self):
        with patch.dict(self.module.os.environ, {"COPILOT_CLI_ENABLED_FEATURE_FLAGS": "EXTENSIONS",
                                                "PATH": "workshop-path"}, clear=True):
            env = self.module.sandbox_runtime_env()
        self.assertEqual(set(env["COPILOT_CLI_ENABLED_FEATURE_FLAGS"].split(",")), {"EXTENSIONS", "SANDBOX"})
        self.assertEqual(env["PATH"], "workshop-path")


class TraceTests(unittest.TestCase):
    def test_success_requires_start_completion_id_result_and_no_error(self):
        trace = ToolTrace()
        trace.record(completed("tool-1", "[]"))
        self.assertIsNone(trace.successful_content("tool-1"))
        trace.record(ToolExecutionStartData(tool_call_id="other", tool_name="view"))
        self.assertIsNone(trace.successful_content("tool-1"))
        trace.record(ToolExecutionStartData(tool_call_id="tool-1", tool_name="view"))
        self.assertEqual(trace.successful_content("tool-1"), "[]")
        trace.completed["tool-1"].error = ToolExecutionCompleteError(message="failed")
        self.assertIsNone(trace.successful_content("tool-1"))


class ConsoleInputTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        console_input.reset_input_state()

    async def test_success_eof_and_timeout_fail_closed_without_competing_reader(self):
        with patch("builtins.input", return_value=" errors "):
            self.assertEqual(await console_input.read_answer("Focus: ", timeout=1), "errors")
        console_input.reset_input_state()
        with patch("builtins.input", side_effect=EOFError):
            with self.assertRaises(EOFError):
                await console_input.read_answer("Focus: ", timeout=1)
        with self.assertRaises(EOFError):
            await console_input.read_answer("No second reader: ", timeout=1)
        console_input.reset_input_state()
        with patch.object(console_input.threading, "Thread") as thread:
            with self.assertRaises(TimeoutError):
                await console_input.read_answer("Focus: ", timeout=0.001)
            self.assertTrue(thread.call_args.kwargs["daemon"])
            with self.assertRaises(EOFError):
                await console_input.read_answer("No second reader: ", timeout=1)
            self.assertEqual(thread.call_count, 1)

    async def test_cancellation_closes_input_and_propagates(self):
        with patch.object(console_input.threading, "Thread") as thread:
            task = asyncio.create_task(console_input.read_answer("Focus: ", timeout=10))
            await asyncio.sleep(0)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            with self.assertRaises(EOFError):
                await console_input.read_answer("No second reader: ", timeout=1)
            self.assertEqual(thread.call_count, 1)


class SDKContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_send_and_wait_timeout_and_listener_cleanup(self):
        session = CopilotSession("test", Mock())
        session.send = AsyncMock()
        with self.assertRaises(TimeoutError):
            await session.send_and_wait("mock", timeout=0.001)
        self.assertFalse(session._event_handlers)

    async def test_real_send_and_wait_idle_none_message_and_error(self):
        for payloads, expected in (
            ([SessionIdleData()], None),
            ([AssistantMessageData(content="answer", message_id="m"), SessionIdleData()], "answer"),
            ([SessionErrorData(error_type="test", message="runtime failed")], RuntimeError),
        ):
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

    def test_pinned_sdk_and_current_public_options_exist(self):
        self.assertIn("github-copilot-sdk==1.0.13", (ROOT / "requirements.txt").read_text())
        config = tomllib.loads((ROOT / "pyproject.toml").read_text())
        self.assertIn("github-copilot-sdk==1.0.13", config["project"]["dependencies"])
        self.assertIn("client_info", inspect.signature(CopilotClient).parameters)
        for connection in (RuntimeConnection.for_stdio(path="vendor/copilot"),
                           RuntimeConnection.for_uri("localhost:4321")):
            inspect.signature(CopilotClient).bind(connection=connection)
        for method in (CopilotClient.create_session, CopilotClient.resume_session):
            for option in ("ask_user_variant", "github_token_provider", "managed_settings", "on_elicitation_request"):
                self.assertIn(option, inspect.signature(method).parameters)
        self.assertTrue(hasattr(CopilotSession, "set_auto_tier"))
        self.assertIn("bearer_token_provider", ProviderConfig.__annotations__)
        self.assertIn("on_user_prompt_transformed", SessionHooks.__annotations__)
        self.assertIn("on_post_tool_use_failure", SessionHooks.__annotations__)
        self.assertEqual(SandboxConfig(enabled=True, allow_bypass=True).to_dict(),
                         {"enabled": True, "allowBypass": True})


if __name__ == "__main__":
    unittest.main()
