"""Smoke test the fictional mock's four-tool contract over Streamable HTTP.

Usage: python test_client.py [url] (default http://127.0.0.1:8000/mcp).
Use only a trusted mock endpoint and nonsensitive demonstration inputs.
"""

import asyncio
import json
import sys
import time
from urllib.parse import urlsplit

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

EXPECTED_TOOLS = {"list_knowledge_domains", "search_knowledge", "get_document", "ask_knowledge"}


def check_provenance(result: dict) -> None:
    if result.get("source") != "mock-knowledge" or result.get("demonstration_data") is not True:
        raise AssertionError("Missing fictional mock provenance")


def check_document(document: dict) -> None:
    check_provenance(document)
    if not document.get("handle") or urlsplit(document["url"]).netloc != "example.com":
        raise AssertionError("Missing handle or unexpected fixture citation host")


async def smoke_session(session: ClientSession) -> None:
    """Reusable assertions for a real initialized MCP client session."""
    tools = [tool.name for tool in (await session.list_tools()).tools]
    if set(tools) != EXPECTED_TOOLS or len(tools) != 4:
        raise AssertionError(f"Unexpected tools: {tools}")
    print(f"Tools: {tools}")

    async def call(name: str, arguments: dict):
        start = time.perf_counter()
        async with asyncio.timeout(30):
            result = await session.call_tool(name, arguments)
        if result.isError:
            raise AssertionError(f"{name} returned a tool error")
        # Newer SDKs wrap list results; text content supports older SDK clients.
        payload = result.structuredContent
        if payload is None:
            texts = [item.text for item in result.content if item.type == "text"]
            payload = json.loads(texts[0]) if len(texts) == 1 else [json.loads(text) for text in texts]
        if name == "list_knowledge_domains" and isinstance(payload, dict):
            payload = payload["result"]
        print(f"{name}: PASS ({time.perf_counter() - start:.2f}s)")
        return payload

    domains = await call("list_knowledge_domains", {})
    if not isinstance(domains, list) or "onboarding" not in domains:
        raise AssertionError("Domain discovery must return a list including onboarding")
    search = await call("search_knowledge", {"query": "onboarding", "domain": "onboarding", "top": 3})
    check_provenance(search)
    documents = search["documents"]
    if not documents or len(documents) > 3:
        raise AssertionError("Expected bounded onboarding search results")
    for document in documents:
        check_document(document)
    document = await call("get_document", {"handle": documents[0]["handle"]})
    check_document(document)
    if document != documents[0]:
        raise AssertionError("Document retrieval differs from search metadata")
    answer = await call("ask_knowledge", {"question": "onboarding", "domain": "onboarding"})
    check_provenance(answer)
    if not answer["answer"] or not answer["citations"]:
        raise AssertionError("Expected a cited fictional answer")
    for citation in answer["citations"]:
        check_document(citation)
        matching = next((doc for doc in documents if doc["handle"] == citation["handle"]), None)
        if matching is None or any(citation[key] != matching[key] for key in matching):
            raise AssertionError("Answer citation differs from returned fixture")
    for name, arguments, empty_key in (
        ("search_knowledge", {"query": "zzzznomatch"}, "documents"),
        ("ask_knowledge", {"question": "zzzznomatch"}, "citations"),
    ):
        empty = await call(name, arguments)
        check_provenance(empty)
        if empty[empty_key] != []:
            raise AssertionError("No-match query unexpectedly returned evidence")
    missing = await call("get_document", {"handle": "demo/missing"})
    check_provenance(missing)
    if "error" not in missing:
        raise AssertionError("Missing document must report an evidence gap")


async def main(url: str = "http://127.0.0.1:8000/mcp") -> None:
    async with streamable_http_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            info = await session.initialize()
            print(f"Connected: {info.serverInfo.name}")
            await smoke_session(session)
            print("PASS: all four tools, fixture citations, provenance, and no-result paths")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/mcp"))
