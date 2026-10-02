"""Contract and security regression tests using the installed MCP SDK.

Run with: python -m unittest discover -s mock-mcp-server -p test_server.py -v
No fake SDK fallback: install requirements first. The HTTP smoke test starts and
stops its own loopback server on an available port, without any external service.
"""

import asyncio
import os
import socket
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

import httpx
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.transport_security import TransportSecurityMiddleware
from starlette.requests import Request

# Tests do not depend on the launching shell's optional tunnel configuration.
with patch.dict(os.environ, {"PORT": "8000", "MCP_ALLOWED_HOSTS": "", "MCP_ALLOWED_ORIGINS": ""}):
    import server

import test_client


class ContractTests(unittest.TestCase):
    def assert_provenance(self, value):
        self.assertEqual(value["source"], "mock-knowledge")
        self.assertIs(value["demonstration_data"], True)

    def test_domains_are_list_and_defensive_copy(self):
        domains = server.list_knowledge_domains()
        self.assertEqual(domains, ["onboarding", "project-planning", "service-operations"])
        domains.clear()
        self.assertEqual(len(server.list_knowledge_domains()), 3)

    def test_all_fixtures_are_fictional_with_example_citations(self):
        self.assertEqual(len({doc["handle"] for doc in server.DOCS}), len(server.DOCS))
        for fixture in server.DOCS:
            with self.subTest(handle=fixture["handle"]):
                doc = server.get_document(fixture["handle"])
                self.assert_provenance(doc)
                self.assertTrue(doc["title"].startswith("Fictional "))
                self.assertIn("fictional", doc["summary"].lower())
                self.assertTrue(doc["handle"].startswith("demo/"))
                self.assertEqual(urlsplit(doc["url"]).netloc, "example.com")
                self.assertEqual(urlsplit(doc["url"]).scheme, "https")
                self.assertNotIn("keywords", doc)
                self.assertNotIn("countries", doc)

    def test_search_provenance_domain_filter_and_top(self):
        for domain in server.DOMAINS:
            result = server.search_knowledge(domain, domain=domain, top=1)
            self.assert_provenance(result)
            self.assertEqual(len(result["documents"]), 1)
            self.assertEqual(result["documents"][0]["domain"], domain)
            self.assert_provenance(result["documents"][0])

    def test_default_top_and_stable_order(self):
        query = "planning onboarding service"
        first = server.search_knowledge(query)
        self.assertEqual(len(first["documents"]), 3)
        self.assertEqual(first, server.search_knowledge(query))
        self.assertEqual(len(server.search_knowledge(query, top=10)["documents"]), len(server.DOCS))

    def test_search_documents_match_lookup(self):
        for doc in server.search_knowledge("planning onboarding service", top=10)["documents"]:
            self.assertEqual(doc, server.get_document(doc["handle"]))

    def test_answer_is_grounded_and_citations_have_provenance(self):
        answer = server.ask_knowledge("onboarding", domain="onboarding")
        self.assert_provenance(answer)
        self.assertIn("Fictional demonstration data", answer["answer"])
        self.assertTrue(answer["citations"])
        for index, citation in enumerate(answer["citations"], 1):
            self.assert_provenance(citation)
            self.assertEqual(citation["n"], index)
            self.assertIn(f"[{index}]", answer["answer"])
            doc = server.get_document(citation["handle"])
            self.assertIn(doc["summary"], answer["answer"])
            self.assertEqual({k: v for k, v in citation.items() if k != "n"}, doc)

    def test_no_results_all_paths_preserve_provenance(self):
        search = server.search_knowledge("zzzznomatch")
        answer = server.ask_knowledge("zzzznomatch")
        missing = server.get_document("demo/missing")
        for value in (search, answer, missing):
            self.assert_provenance(value)
        self.assertEqual(search["documents"], [])
        self.assertEqual(answer["citations"], [])
        self.assertIn("No fictional", answer["answer"])
        self.assertIn("error", missing)
        self.assertNotIn("url", missing)
        self.assertEqual(server.search_knowledge("onboarding", "project-planning")["documents"], [])

    def test_query_and_question_bounds(self):
        for function in (server.search_knowledge, server.ask_knowledge):
            for bad in ("", " \t\n", "x" * 1001, None, 1):
                with self.subTest(function=function.__name__, value_type=type(bad).__name__), self.assertRaises(ValueError):
                    function(bad)
            self.assertEqual(function("x" * 1000)["source"], "mock-knowledge")
            function("x")

    def test_top_bounds_and_strict_integer(self):
        for bad in (0, -1, 11, True, False, 1.5, "3", None):
            with self.subTest(top=bad), self.assertRaises(ValueError):
                server.search_knowledge("onboarding", top=bad)
        for valid in (1, 10):
            self.assertLessEqual(len(server.search_knowledge("onboarding", top=valid)["documents"]), valid)

    def test_unknown_domain_is_input_error(self):
        for bad in ("", "unknown", "ONBOARDING", "x" * 1001):
            with self.subTest(domain=bad[:20]), self.assertRaises(ValueError):
                server.search_knowledge("onboarding", domain=bad)
            with self.assertRaises(ValueError):
                server.ask_knowledge("onboarding", domain=bad)

    def test_handle_bounds(self):
        for bad in ("", " ", "x" * 129, None):
            with self.subTest(handle=bad), self.assertRaises(ValueError):
                server.get_document(bad)
        self.assertIn("error", server.get_document("x" * 128))


class TransportSettingsTests(unittest.TestCase):
    def test_defaults_are_exact_loopback_and_enabled(self):
        settings = server.build_transport_security(environ={})
        self.assertTrue(settings.enable_dns_rebinding_protection)
        self.assertEqual(settings.allowed_hosts, ["127.0.0.1:8000", "localhost:8000", "[::1]:8000"])
        self.assertEqual(settings.allowed_origins, [f"http://{host}" for host in settings.allowed_hosts])
        self.assertFalse(any("*" in value for value in settings.allowed_hosts + settings.allowed_origins))
        self.assertEqual(server.mcp.settings.host, "127.0.0.1")
        self.assertTrue(server.mcp.settings.transport_security.enable_dns_rebinding_protection)

    def test_configured_port_remains_narrow(self):
        settings = server.build_transport_security(8123, {})
        self.assertIn("localhost:8123", settings.allowed_hosts)
        self.assertNotIn("localhost:8000", settings.allowed_hosts)
        for port in (0, -1, 65536, True, "8000"):
            with self.subTest(port=port), self.assertRaises(ValueError):
                server.build_transport_security(port, {})

    def test_exact_tunnel_additions_trim_and_deduplicate(self):
        settings = server.build_transport_security(environ={
            "MCP_ALLOWED_HOSTS": " demo.example.com, demo.example.com:443, demo.example.com ",
            "MCP_ALLOWED_ORIGINS": "https://demo.example.com, https://demo.example.com:443",
        })
        self.assertEqual(settings.allowed_hosts[-2:], ["demo.example.com", "demo.example.com:443"])
        self.assertEqual(settings.allowed_origins[-2:], ["https://demo.example.com", "https://demo.example.com:443"])
        self.assertTrue(settings.enable_dns_rebinding_protection)

    def test_invalid_extra_hosts_fail_closed(self):
        for bad in (
            "*", "*.example.com", "demo.example.com:*", "https://demo.example.com",
            "demo.example.com/path", "user:secret@demo.example.com", "demo.example.com?x=1",
            "demo.example.com#fragment", "demo.example.com:0", "demo.example.com:65536",
            "demo.example.com:0443", "demo.example.com:abc", "-bad.example.com",
            "bad..example.com", "bad_host", "demo.example.com,", ",demo.example.com",
            "demo.example.com,,other.example.com", "demo.example.com\nother.example.com",
            "[::1", "::1", "[::1]:*", "999.999.999.999", "démø.example.com",
        ):
            with self.subTest(host=bad), self.assertRaisesRegex(ValueError, "MCP_ALLOWED_HOSTS"):
                server.build_transport_security(environ={"MCP_ALLOWED_HOSTS": bad})

    def test_invalid_extra_origins_fail_closed(self):
        for bad in (
            "*", "null", "https://*.example.com", "https://demo.example.com:*",
            "http://demo.example.com", "ftp://demo.example.com", "demo.example.com",
            "https://demo.example.com/", "https://demo.example.com/mcp",
            "https://demo.example.com?", "https://demo.example.com#",
            "https://demo.example.com:65536", "https://user:secret@demo.example.com",
            "https://demo.example.com,", "https://demo.exa\nmple.com",
        ):
            with self.subTest(origin=bad), self.assertRaisesRegex(ValueError, "MCP_ALLOWED_ORIGINS"):
                server.build_transport_security(environ={"MCP_ALLOWED_ORIGINS": bad})

    def test_blank_settings_are_optional(self):
        self.assertEqual(
            server.build_transport_security(environ={}).model_dump(),
            server.build_transport_security(environ={"MCP_ALLOWED_HOSTS": " ", "MCP_ALLOWED_ORIGINS": ""}).model_dump(),
        )

    def test_configuration_errors_do_not_echo_secrets(self):
        with self.assertRaises(ValueError) as error:
            server.build_transport_security(environ={"MCP_ALLOWED_HOSTS": "user:accidental-secret@example.com"})
        self.assertNotIn("accidental-secret", str(error.exception))


class SDKTests(unittest.IsolatedAsyncioTestCase):
    async def test_discovery_signatures_and_schema_bounds(self):
        tools = {tool.name: tool for tool in await server.mcp.list_tools()}
        self.assertEqual(set(tools), test_client.EXPECTED_TOOLS)
        for name, parameters in (
            ("list_knowledge_domains", set()), ("search_knowledge", {"query", "domain", "top"}),
            ("get_document", {"handle"}), ("ask_knowledge", {"question", "domain"}),
        ):
            self.assertEqual(set(tools[name].inputSchema["properties"]), parameters)
        search = tools["search_knowledge"].inputSchema
        self.assertEqual(search["required"], ["query"])
        self.assertEqual(search["properties"]["query"]["maxLength"], 1000)
        self.assertEqual(search["properties"]["top"]["minimum"], 1)
        self.assertEqual(search["properties"]["top"]["maximum"], 10)
        self.assertEqual(search["properties"]["top"]["default"], 3)
        self.assertEqual(tools["ask_knowledge"].inputSchema["properties"]["question"]["maxLength"], 1000)

    async def test_sdk_rejects_out_of_bounds_inputs(self):
        for name, arguments in (
            ("search_knowledge", {"query": ""}),
            ("search_knowledge", {"query": "x" * 1001}),
            ("search_knowledge", {"query": "onboarding", "top": 0}),
            ("search_knowledge", {"query": "onboarding", "top": 11}),
            ("search_knowledge", {"query": "onboarding", "top": True}),
            ("search_knowledge", {"query": "onboarding", "top": "3"}),
            ("search_knowledge", {"query": "onboarding", "domain": "unknown"}),
            ("ask_knowledge", {"question": " "}),
            ("ask_knowledge", {"question": "x" * 1001}),
            ("get_document", {"handle": "x" * 129}),
        ):
            with self.subTest(tool=name, keys=list(arguments)), self.assertRaises(ToolError):
                await server.mcp.call_tool(name, arguments)

    async def test_actual_sdk_transport_header_validation(self):
        middleware = TransportSecurityMiddleware(server.build_transport_security(environ={
            "MCP_ALLOWED_HOSTS": "demo.example.com:443",
            "MCP_ALLOWED_ORIGINS": "https://demo.example.com",
        }))

        async def validate(host, origin=None, content_type="application/json"):
            headers = [(b"content-type", content_type.encode())]
            if host is not None:
                headers.append((b"host", host.encode()))
            if origin is not None:
                headers.append((b"origin", origin.encode()))
            request = Request({"type": "http", "method": "POST", "path": "/mcp", "headers": headers})
            return await middleware.validate_request(request, is_post=True)

        for host in ("127.0.0.1:8000", "localhost:8000", "[::1]:8000", "demo.example.com:443"):
            self.assertIsNone(await validate(host))
        self.assertIsNone(await validate("demo.example.com:443", "https://demo.example.com"))
        self.assertIsNone(await validate("127.0.0.1:8000", "http://localhost:8000"))
        for host in (None, "evil.example.com", "localhost:8001", "demo.example.com", "demo.example.com:444", "demo.example.com:443.evil.com"):
            with self.subTest(host=host):
                self.assertEqual((await validate(host)).status_code, 421)
        for origin in ("null", "https://evil.example.com", "https://demo.example.com:443", "https://demo.example.com.evil.com", "http://localhost:8001"):
            with self.subTest(origin=origin):
                self.assertEqual((await validate("127.0.0.1:8000", origin)).status_code, 403)
        self.assertEqual((await validate("127.0.0.1:8000", content_type="text/plain")).status_code, 400)

    async def test_live_http_smoke_and_security_rejections(self):
        # Reserve an available port briefly; the child reports startup through HTTP.
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        env = dict(os.environ, PORT=str(port), HOST="0.0.0.0", MCP_ALLOWED_HOSTS="", MCP_ALLOWED_ORIGINS="")
        process = subprocess.Popen(
            [sys.executable, str(Path(__file__).with_name("server.py"))],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        url = f"http://127.0.0.1:{port}/mcp"
        try:
            async with asyncio.timeout(30):
                async with httpx.AsyncClient(
                    trust_env=False, headers={"Accept": "application/json, text/event-stream"},
                ) as client:
                    while True:
                        if process.poll() is not None:
                            self.fail(f"Mock process exited during startup: {process.returncode}")
                        try:
                            response = await client.post(url, json={})
                            if response.status_code == 400:
                                break
                        except httpx.ConnectError:
                            pass
                        await asyncio.sleep(0.1)
                    rejected_host = await client.post(url, json={}, headers={"Host": "evil.example.com"})
                    self.assertEqual(rejected_host.status_code, 421)
                    rejected_origin = await client.post(url, json={}, headers={"Origin": "https://evil.example.com"})
                    self.assertEqual(rejected_origin.status_code, 403)
                await test_client.main(url)
        finally:
            process.terminate()
            try:
                await asyncio.to_thread(process.wait, timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                await asyncio.to_thread(process.wait)


if __name__ == "__main__":
    unittest.main()