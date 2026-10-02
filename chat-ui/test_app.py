"""Focused security tests. All model/MCP/credential operations are mocked."""

import asyncio
import json
import runpy
import unittest
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from openai.types.chat import ChatCompletionMessage

import app

ENV = {"AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com/",
       "AZURE_OPENAI_DEPLOYMENT": "demo-deployment"}
SETTINGS = app.load_settings(ENV)
ORIGIN = {"Origin": SETTINGS.origin}


def response(calls=None, content="Fictional answer."):
    message = ChatCompletionMessage(role="assistant", content=content, tool_calls=calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def tool_call(name="list_knowledge_domains", arguments="{}", identifier="demo-call"):
    return {"id": identifier, "type": "function",
            "function": {"name": name, "arguments": arguments}}


@contextmanager
def demo_client(responses=None, *, discovery=None, result=None, failure=None, peer="127.0.0.1"):
    completion = AsyncMock(side_effect=failure or responses or [response()])
    model = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=completion)))
    names = list(app.ALLOWED_TOOLS) if discovery is None else discovery
    session = SimpleNamespace(
        list_tools=AsyncMock(return_value=SimpleNamespace(tools=[SimpleNamespace(name=n) for n in names])),
        call_tool=AsyncMock(return_value=result or SimpleNamespace(
            isError=False, content=[SimpleNamespace(type="text", text="fictional fixture")],
        )),
    )

    @asynccontextmanager
    async def connection(_url):
        yield session

    with patch.object(app, "open_mcp", connection), patch.object(app, "create_model_client") as build:
        with TestClient(app.create_app(SETTINGS, model), base_url=SETTINGS.origin,
                        client=(peer, 40000)) as client:
            yield client, session, completion
        build.assert_not_called()


class ConfigurationTests(unittest.TestCase):
    def test_missing_config_has_no_private_fallback(self):
        for env in ({}, {"AZURE_OPENAI_ENDPOINT": ENV["AZURE_OPENAI_ENDPOINT"]},
                    {"AZURE_OPENAI_DEPLOYMENT": "demo"}):
            with self.subTest(env=env), self.assertRaisesRegex(ValueError, "are required"):
                app.load_settings(env)

    def test_defaults_and_explicit_api_version(self):
        self.assertEqual(SETTINGS.mcp_url, "http://127.0.0.1:8000/mcp")
        self.assertEqual(SETTINGS.api_version, "2024-10-21")
        self.assertFalse(SETTINGS.managed_identity)
        actual = app.load_settings(ENV | {"AZURE_OPENAI_API_VERSION": "2025-04-01-preview",
                                         "USE_MANAGED_IDENTITY": "1", "PORT": "8181"})
        self.assertEqual(actual.api_version, "2025-04-01-preview")
        self.assertTrue(actual.managed_identity)
        self.assertEqual(actual.origin, "http://127.0.0.1:8181")

    def test_loopback_mcp_only_by_default(self):
        for url in ("http://127.0.0.1:8000/mcp", "http://localhost:8000/mcp", "http://[::1]:8000/mcp"):
            with self.subTest(url=url):
                self.assertEqual(app.load_settings(ENV | {"MCP_URL": url}).mcp_url, url)
        for url in ("http://example.com/mcp", "https://example.com/mcp", "http://127.0.0.2/mcp",
                    "http://127.0.0.1.example.com/mcp", "http://2130706433/mcp", "ftp://localhost/mcp"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                app.load_settings(ENV | {"MCP_URL": url})

    def test_external_https_requires_exact_approval(self):
        url = "https://example.com/mcp"
        self.assertEqual(app.load_settings(ENV | {"MCP_URL": url, "MCP_APPROVED_HTTPS_URL": url}).mcp_url, url)
        for approved in ("https://example.com/", "https://example.com/mcp/", "*"):
            with self.subTest(approved=approved), self.assertRaises(ValueError):
                app.load_settings(ENV | {"MCP_URL": url, "MCP_APPROVED_HTTPS_URL": approved})
        with self.assertRaises(ValueError):
            app.load_settings(ENV | {"MCP_URL": "http://example.com/mcp",
                                     "MCP_APPROVED_HTTPS_URL": "http://example.com/mcp"})
        rejected_urls = ["https://*.example.com/mcp", "https://example..com/mcp"]
        rejected_urls += ["https://%65xample.com/mcp", "https://[::1%25demo]/mcp"]
        for rejected in rejected_urls:
            config = ENV | {"MCP_URL": rejected, "MCP_APPROVED_HTTPS_URL": rejected}
            self.assertRaises(ValueError, app.load_settings, config)

    def test_unsafe_config_is_rejected_without_echo(self):
        for key, value in (
            ("AZURE_OPENAI_ENDPOINT", "http://example.com"),
            ("AZURE_OPENAI_ENDPOINT", "https://example.com/private"),
            ("MCP_URL", "http://user:SECRET@127.0.0.1/mcp"),
            ("MCP_URL", "http://127.0.0.1/mcp?token=SECRET"),
            ("MCP_URL", "http://127.0.0.1/mcp#SECRET"),
            ("MCP_URL", "http://127.0.0.1:99999/mcp"),
            ("MCP_URL", "http://127.0.0.1\\@example.com/mcp"),
            ("MCP_URL", "http://127.0.0.1/\nSECRET"),
            ("USE_MANAGED_IDENTITY", "true"), ("PORT", "0"), ("PORT", "65536"),
            ("PORT", "SECRET"), ("AZURE_OPENAI_API_VERSION", ""),
            ("AZURE_OPENAI_DEPLOYMENT", "demo/SECRET"),
        ):
            with self.subTest(key=key, value=value):
                with self.assertRaises(ValueError) as caught:
                    app.load_settings(ENV | {key: value})
                self.assertNotIn("SECRET", str(caught.exception))

    def test_legacy_mcp_variable_is_not_used(self):
        self.assertEqual(app.load_settings(ENV | {"TELLUS_MCP_URL": "https://example.com/"}).mcp_url,
                         SETTINGS.mcp_url)

    def test_explicit_credential_selection_and_sdk_options(self):
        for managed in (False, True):
            with self.subTest(managed=managed), patch.object(app, "AzureCliCredential") as cli, \
                    patch.object(app, "ManagedIdentityCredential") as mi, \
                    patch.object(app, "get_bearer_token_provider") as token, \
                    patch.object(app, "AsyncAzureOpenAI") as sdk, \
                    patch.object(app.httpx, "AsyncClient") as http:
                settings = app.load_settings(ENV | {"USE_MANAGED_IDENTITY": "1" if managed else "0"})
                app.create_model_client(settings)
                selected, other = (mi, cli) if managed else (cli, mi)
                selected.assert_called_once_with()
                other.assert_not_called()
                token.assert_called_once_with(selected.return_value, "https://cognitiveservices.azure.com/.default")
                self.assertEqual(sdk.call_args.kwargs["api_version"], settings.api_version)
                self.assertEqual(sdk.call_args.kwargs["max_retries"], 0)
                http.assert_called_once_with(trust_env=False, follow_redirects=False, timeout=20)

    def test_entrypoint_fixes_loopback_and_disables_proxy_trust_and_verbose_logs(self):
        with patch.dict(app.os.environ, ENV | {"PORT": "8181"}, clear=True), \
                patch.object(app.uvicorn, "run") as run:
            runpy.run_path(str(Path(app.__file__)), run_name="__main__")
            run.assert_called_once()
            self.assertEqual(run.call_args.kwargs, {
                "host": "127.0.0.1", "port": 8181, "proxy_headers": False,
                "access_log": False, "log_level": "critical",
            })

    def test_entrypoint_fails_before_listener_without_configuration(self):
        with patch.dict(app.os.environ, {}, clear=True), patch.object(app.uvicorn, "run") as run:
            with self.assertRaisesRegex(SystemExit, "are required"):
                runpy.run_path(str(Path(app.__file__)), run_name="__main__")
            run.assert_not_called()


class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_mcp_disables_redirects_and_environment_proxies(self):
        session = SimpleNamespace(initialize=AsyncMock())
        read, write, http = object(), object(), object()

        @asynccontextmanager
        async def transport(url, *, http_client):
            self.assertEqual(url, SETTINGS.mcp_url)
            self.assertIs(http_client, http)
            yield read, write, lambda: None

        @asynccontextmanager
        async def client_session(actual_read, actual_write):
            self.assertIs(actual_read, read)
            self.assertIs(actual_write, write)
            yield session

        with patch.object(app.httpx, "AsyncClient") as factory, \
                patch.object(app, "streamable_http_client", transport), \
                patch.object(app, "ClientSession", client_session):
            factory.return_value.__aenter__.return_value = http
            async with app.open_mcp(SETTINGS.mcp_url) as actual:
                self.assertIs(actual, session)
                session.initialize.assert_awaited_once_with()
            factory.assert_called_once_with(trust_env=False, follow_redirects=False, timeout=20)


class ToolContractTests(unittest.TestCase):
    def test_discovery_filters_deduplicates_and_uses_local_schemas(self):
        discovered = [SimpleNamespace(name=n, inputSchema={"malicious": True}, description="SECRET")
                      for n in list(app.ALLOWED_TOOLS) + ["delete_everything", "ask_knowledge"]]
        tools = app.discover_tools(discovered)
        self.assertEqual({t["function"]["name"] for t in tools}, app.ALLOWED_TOOLS)
        self.assertEqual(len(tools), 4)
        for tool in tools:
            self.assertFalse(tool["function"]["parameters"]["additionalProperties"])
        self.assertNotIn("SECRET", json.dumps(tools))
        self.assertNotIn("malicious", json.dumps(tools))

    def test_arguments_reject_unknown_keys_types_lengths_and_undiscovered_names(self):
        invalid = [
            ("delete_everything", "{}"), ("list_knowledge_domains", '{"extra":1}'),
            ("search_knowledge", '{"query":"demo","extra":1}'),
            ("search_knowledge", '{"query":"demo","top":true}'),
            ("search_knowledge", '{"query":"demo","top":"3"}'),
            ("search_knowledge", '{"query":"demo","top":11}'),
            ("search_knowledge", '{"query":" "}'), ("ask_knowledge", "[]"),
            ("ask_knowledge", "null"), ("ask_knowledge", "not JSON"),
            ("ask_knowledge", '{"question":3}'), ("ask_knowledge", '{}'),
            ("get_document", json.dumps({"handle": "x" * 129})),
            ("ask_knowledge", json.dumps({"question": "x" * 1001})),
            ("ask_knowledge", " " * (app.MAX_TOOL_ARGUMENT_BYTES + 1)),
        ]
        for name, raw in invalid:
            with self.subTest(name=name, raw=raw[:50]), self.assertRaises(ValueError):
                app.validate_arguments(name, raw, set(app.ALLOWED_TOOLS))
        with self.assertRaises(ValueError):
            app.validate_arguments("get_document", '{"handle":"demo"}', {"ask_knowledge"})

    def test_valid_arguments_preserve_contract(self):
        for name, args in (
            ("list_knowledge_domains", {}), ("get_document", {"handle": "demo/planning"}),
            ("search_knowledge", {"query": "planning", "top": 10, "domain": None}),
            ("ask_knowledge", {"question": "planning", "domain": "project-planning"}),
        ):
            with self.subTest(name=name):
                self.assertEqual(app.validate_arguments(name, json.dumps(args), set(app.ALLOWED_TOOLS)), args)


class BrowserAndRequestTests(unittest.TestCase):
    def test_local_page_has_no_cors_and_is_not_copilot(self):
        with demo_client() as (client, _, completion):
            result = client.get("/")
            self.assertEqual(result.status_code, 200)
            self.assertIn("not Microsoft 365 Copilot", result.text)
            self.assertIn("FICTIONAL DATA", result.text)
            self.assertNotIn("access-control-allow-origin", result.headers)
            self.assertEqual(result.headers["cache-control"], "no-store")
            self.assertIn("frame-ancestors 'none'", result.headers["content-security-policy"])
            completion.assert_not_awaited()

    def test_cross_origin_missing_origin_and_rebinding_blocked(self):
        with demo_client() as (client, session, completion):
            for headers in ({}, {"Origin": "null"}, {"Origin": "https://example.com"},
                            {"Origin": "http://localhost:8080"},
                            ORIGIN | {"Host": "example.com:8080"},
                            ORIGIN | {"Host": "127.0.0.1:8081"},
                            ORIGIN | {"Sec-Fetch-Site": "cross-site"}):
                with self.subTest(headers=headers):
                    result = client.post("/api/chat", json={"message": "demo"}, headers=headers)
                    self.assertEqual(result.status_code, 403)
                    self.assertNotIn("access-control-allow-origin", result.headers)
            self.assertEqual(client.get("/", headers={"Host": "example.com"}).status_code, 403)
            self.assertEqual(client.options("/api/chat", headers={"Origin": "https://example.com",
                                                                 "Access-Control-Request-Method": "POST"}).status_code, 403)
            completion.assert_not_awaited()
            session.list_tools.assert_not_awaited()

    def test_duplicate_host_and_origin_rejected(self):
        with demo_client() as (client, _, completion):
            for headers in (
                [("Host", SETTINGS.authority), ("Host", "example.com"), ("Origin", SETTINGS.origin)],
                [("Origin", SETTINGS.origin), ("Origin", "https://example.com")],
            ):
                self.assertEqual(client.post("/api/chat", json={"message": "demo"}, headers=headers).status_code, 403)
            completion.assert_not_awaited()

    def test_nonloopback_peer_and_forwarded_headers_do_not_grant_access(self):
        with demo_client(peer="192.0.2.1") as (client, _, completion):
            result = client.post("/api/chat", json={"message": "demo"},
                                 headers=ORIGIN | {"X-Forwarded-For": "127.0.0.1"})
            self.assertEqual(result.status_code, 403)
            completion.assert_not_awaited()

    def test_invalid_messages_sanitized_before_upstream(self):
        with demo_client() as (client, session, completion):
            for body in ({"message": ""}, {"message": " "}, {"message": "x" * 2001},
                         {"message": 123}, {"message": "demo", "SECRET": "secret"}, {}, []):
                with self.subTest(body=str(body)[:50]):
                    result = client.post("/api/chat", json=body, headers=ORIGIN)
                    self.assertEqual(result.status_code, 400)
                    self.assertEqual(set(result.json()), {"detail"})
                    self.assertNotIn("SECRET", result.text)
            result = client.post("/api/chat", content="not JSON SECRET",
                                 headers=ORIGIN | {"Content-Type": "application/json"})
            self.assertEqual(result.status_code, 400)
            completion.assert_not_awaited()
            session.list_tools.assert_not_awaited()

    def test_body_size_and_media_type(self):
        with demo_client() as (client, _, completion):
            self.assertEqual(client.post("/api/chat", content=b"x" * (app.MAX_REQUEST_BYTES + 1),
                                         headers=ORIGIN | {"Content-Type": "application/json"}).status_code, 413)
            self.assertEqual(client.post("/api/chat", content="demo", headers=ORIGIN).status_code, 415)
            completion.assert_not_awaited()

    def test_message_boundary_and_ungrounded_answer(self):
        with demo_client() as (client, _, _):
            result = client.post("/api/chat", json={"message": "x" * 2000}, headers=ORIGIN)
            self.assertEqual(result.status_code, 200)
            self.assertFalse(result.json()["tool_evidence"])
            self.assertEqual(result.json()["trace"], [])
            self.assertTrue(result.json()["demonstration_data"])


class ExecutionTests(unittest.TestCase):
    def test_success_trace_contains_only_name_status_and_demo_metadata(self):
        result = SimpleNamespace(isError=False, content=[SimpleNamespace(type="text", text="PRIVATE_RESULT")])
        replies = [response([tool_call("ask_knowledge", '{"question":"PRIVATE_ARGS"}')]), response()]
        with demo_client(replies, result=result) as (client, session, completion):
            reply = client.post("/api/chat", json={"message": "demo"}, headers=ORIGIN)
            self.assertEqual(reply.status_code, 200)
            data = reply.json()
            self.assertEqual(data["trace"], [{"tool": "ask_knowledge", "error": False, "demonstration_data": True}])
            self.assertTrue(data["tool_evidence"])
            self.assertIn("Fictional demonstration data", data["answer"])
            for private in ("PRIVATE_ARGS", "PRIVATE_RESULT", SETTINGS.endpoint, SETTINGS.mcp_url, SETTINGS.deployment):
                self.assertNotIn(private, reply.text)
            session.call_tool.assert_awaited_once_with("ask_knowledge", {"question": "PRIVATE_ARGS"})
            advertised = completion.call_args_list[0].kwargs["tools"]
            self.assertEqual({t["function"]["name"] for t in advertised}, app.ALLOWED_TOOLS)
            self.assertNotIn("reasoning_effort", completion.call_args.kwargs)

    def test_invalid_batch_executes_nothing(self):
        for call in (tool_call("delete_everything"), tool_call("ask_knowledge", '{"question":"demo","SECRET":1}'),
                     tool_call("ask_knowledge", "not JSON")):
            with self.subTest(call=call), demo_client([response([tool_call(), call])]) as (client, session, _):
                result = client.post("/api/chat", json={"message": "demo"}, headers=ORIGIN)
                self.assertEqual(result.status_code, 502)
                self.assertEqual(result.json(), {"detail": app.UPSTREAM_ERROR})
                session.call_tool.assert_not_awaited()

    def test_undiscovered_allowed_tool_not_invoked(self):
        with demo_client([response([tool_call("get_document", '{"handle":"demo"}')])],
                         discovery=["ask_knowledge"]) as (client, session, _):
            self.assertEqual(client.post("/api/chat", json={"message": "demo"}, headers=ORIGIN).status_code, 502)
            session.call_tool.assert_not_awaited()

    def test_no_approved_tools_fails_before_model(self):
        with demo_client(discovery=["delete_everything"]) as (client, _, completion):
            self.assertEqual(client.post("/api/chat", json={"message": "demo"}, headers=ORIGIN).status_code, 502)
            completion.assert_not_awaited()

    def test_round_limit(self):
        replies = [response([tool_call()]) for _ in range(app.MAX_TOOL_ROUNDS + 1)]
        with demo_client(replies) as (client, session, completion):
            result = client.post("/api/chat", json={"message": "demo"}, headers=ORIGIN)
            self.assertEqual(result.json(), {"detail": app.LIMIT_ERROR})
            self.assertEqual(result.status_code, 502)
            self.assertEqual(session.call_tool.await_count, app.MAX_TOOL_ROUNDS)
            self.assertEqual(completion.await_count, app.MAX_TOOL_ROUNDS + 1)

    def test_total_call_limit_before_batch(self):
        replies = [response([tool_call(identifier=str(i)) for i in range(5)]),
                   response([tool_call(identifier=str(i)) for i in range(4)])]
        with demo_client(replies) as (client, session, _):
            result = client.post("/api/chat", json={"message": "demo"}, headers=ORIGIN)
            self.assertEqual(result.json(), {"detail": app.LIMIT_ERROR})
            self.assertEqual(session.call_tool.await_count, 5)

    def test_upstream_exceptions_sanitized(self):
        for upstream in ("model", "discovery", "tool", "connection"):
            with self.subTest(upstream=upstream), demo_client([response([tool_call()])]) as (client, session, completion):
                error = RuntimeError("SECRET https://private.example/ deployment auth credential detail")
                if upstream == "model":
                    completion.side_effect = error
                elif upstream == "discovery":
                    session.list_tools.side_effect = error
                elif upstream == "tool":
                    session.call_tool.side_effect = error
                if upstream == "connection":
                    @asynccontextmanager
                    async def fail(_url):
                        raise error
                        yield  # pragma: no cover
                    with patch.object(app, "open_mcp", fail):
                        result = client.post("/api/chat", json={"message": "demo"}, headers=ORIGIN)
                else:
                    result = client.post("/api/chat", json={"message": "demo"}, headers=ORIGIN)
                self.assertEqual(result.status_code, 502)
                self.assertEqual(result.json(), {"detail": app.UPSTREAM_ERROR})
                self.assertNotIn("SECRET", result.text)

    def test_tool_error_content_not_sent_to_model_or_trace(self):
        tool_result = SimpleNamespace(isError=True, content=[SimpleNamespace(type="text", text="SECRET upstream error")])
        with demo_client([response([tool_call()]), response()], result=tool_result) as (client, _, completion):
            result = client.post("/api/chat", json={"message": "demo"}, headers=ORIGIN)
            self.assertEqual(result.status_code, 200)
            self.assertTrue(result.json()["trace"][0]["error"])
            self.assertFalse(result.json()["tool_evidence"])
            self.assertNotIn("SECRET", result.text)
            messages = completion.call_args.kwargs["messages"]
            self.assertEqual(messages[-1]["content"], "Demo tool failed.")

    def test_deadline_returns_generic_error(self):
        async def slow(**_kwargs):
            await asyncio.sleep(1)
            return response()
        with demo_client() as (client, _, completion), patch.object(app, "REQUEST_TIMEOUT_SECONDS", 0.01):
            completion.side_effect = slow
            result = client.post("/api/chat", json={"message": "demo"}, headers=ORIGIN)
            self.assertEqual(result.status_code, 502)
            self.assertEqual(result.json(), {"detail": app.UPSTREAM_ERROR})

    def test_oversized_tool_result_and_answer(self):
        tool_result = SimpleNamespace(isError=False, content=[SimpleNamespace(type="text", text="x" * 16001)])
        with demo_client([response([tool_call()])], result=tool_result) as (client, _, _):
            result = client.post("/api/chat", json={"message": "demo"}, headers=ORIGIN)
            self.assertEqual(result.json(), {"detail": app.LIMIT_ERROR})
        with demo_client([response(content="x" * 16001)]) as (client, _, _):
            result = client.post("/api/chat", json={"message": "demo"}, headers=ORIGIN)
            self.assertEqual(result.json(), {"detail": app.UPSTREAM_ERROR})


if __name__ == "__main__":
    unittest.main()