"""Read-only fictional knowledge for the custom chat app demonstration.

No credentials, private documents, real policies, or external retrieval are used.
The listener is always loopback; exact allowlists support approved HTTPS tunnels.
"""

import ipaddress
import os
import re
from collections.abc import Mapping
from typing import Annotated, Any
from urllib.parse import urlsplit

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import Field

MAX_QUERY_LENGTH = 1000
MAX_TOP = 10
PROVENANCE = {"source": "mock-knowledge", "demonstration_data": True}
Query = Annotated[str, Field(min_length=1, max_length=MAX_QUERY_LENGTH)]
Top = Annotated[int, Field(ge=1, le=MAX_TOP, strict=True)]
Handle = Annotated[str, Field(min_length=1, max_length=128)]

DOCS: list[dict[str, Any]] = [
    {
        "handle": "demo/project-planning/launch-plan",
        "title": "Fictional Lantern project launch plan",
        "year": 2026,
        "domain": "project-planning",
        "summary": "In the fictional Lantern project, planning starts with a scope checklist, "
        "milestone owners, and a weekly review of dependencies before each launch rehearsal.",
        "keywords": ["project", "planning", "scope", "milestone", "launch", "dependencies"],
    },
    {
        "handle": "demo/project-planning/risk-review",
        "title": "Fictional Lantern project risk review",
        "year": 2025,
        "domain": "project-planning",
        "summary": "The fictional Lantern planning team keeps a risk register with an owner, "
        "a mitigation task, and a review date for each project dependency.",
        "keywords": ["project", "planning", "risk", "register", "dependencies"],
    },
    {
        "handle": "demo/onboarding/welcome-checklist",
        "title": "Fictional Meadow team onboarding checklist",
        "year": 2026,
        "domain": "onboarding",
        "summary": "Fictional Meadow onboarding pairs each new teammate with a buddy, "
        "uses a sandbox orientation task, and schedules a first-week feedback session.",
        "keywords": ["onboarding", "buddy", "orientation", "welcome", "feedback"],
    },
    {
        "handle": "demo/onboarding/practice-handoff",
        "title": "Fictional Meadow onboarding practice handoff",
        "year": 2025,
        "domain": "onboarding",
        "summary": "The fictional Meadow onboarding exercise uses an invented service ticket "
        "to practice handoffs, record open questions, and confirm who owns the next step.",
        "keywords": ["onboarding", "practice", "handoff", "service", "ticket"],
    },
    {
        "handle": "demo/service-operations/queue-review",
        "title": "Fictional Pebble service operations queue review",
        "year": 2026,
        "domain": "service-operations",
        "summary": "Fictional Pebble service operations groups invented tickets by urgency, "
        "assigns a queue owner, and records a handoff note before each shift change.",
        "keywords": ["service", "operations", "queue", "ticket", "handoff", "shift"],
    },
]
DOMAINS = sorted({doc["domain"] for doc in DOCS})


def _validate_authority(value: str) -> None:
    """Accept only an exact ASCII DNS/IP host, with an optional numeric port."""
    if not value or not value.isascii() or re.search(r"[\s/*\\@?#%]", value):
        raise ValueError("Expected an exact host with optional port; no URL, wildcard, or whitespace")
    if value.startswith("["):
        match = re.fullmatch(r"\[([^\]]+)\](?::([0-9]+))?", value)
        if not match:
            raise ValueError("Invalid bracketed IPv6 host")
        ipaddress.IPv6Address(match[1])
        port = match[2]
    else:
        match = re.fullmatch(r"([^:]+)(?::([0-9]+))?", value)
        if not match:
            raise ValueError("Invalid host or port")
        hostname, port = match.groups()
        if len(hostname) > 253 or any(
            not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
            for label in hostname.split(".")
        ):
            raise ValueError("Invalid DNS host")
        if re.fullmatch(r"[0-9.]+", hostname):
            ipaddress.IPv4Address(hostname)
    if port is not None and (not 1 <= int(port) <= 65535 or str(int(port)) != port):
        raise ValueError("Port must be a canonical integer from 1 to 65535")


def _validate_origin(value: str) -> None:
    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or value != f"{parsed.scheme}://{parsed.netloc}":
        raise ValueError("Origin must be scheme://host[:port], without path, query, or fragment")
    _validate_authority(parsed.netloc)
    if parsed.scheme == "http" and parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("Non-loopback tunnel origins must use HTTPS")


def build_transport_security(
    port: int = 8000, environ: Mapping[str, str] | None = None,
) -> TransportSecuritySettings:
    """Build exact loopback defaults plus validated, explicitly approved additions."""
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("PORT must be an integer from 1 to 65535")
    env = os.environ if environ is None else environ
    hosts = [f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"]
    origins = [f"http://{host}" for host in hosts]
    for name, target, validator in (
        ("MCP_ALLOWED_HOSTS", hosts, _validate_authority),
        ("MCP_ALLOWED_ORIGINS", origins, _validate_origin),
    ):
        raw = env.get(name, "")
        if not raw.strip():
            continue
        for entry in raw.split(","):
            entry = entry.strip()
            try:
                validator(entry)
            except ValueError:
                # Do not echo values that might accidentally contain secrets.
                raise ValueError(f"Invalid {name}: use exact hosts/origins with valid ports; no wildcards or paths") from None
            if entry not in target:
                target.append(entry)
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True, allowed_hosts=hosts, allowed_origins=origins,
    )


def _validate_text(value: str, name: str, limit: int = MAX_QUERY_LENGTH) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{name} must contain 1 to {limit} characters and not be blank")

def _validate_domain(domain: str | None) -> None:
    if domain is not None and domain not in DOMAINS:
        raise ValueError("domain must be a value returned by list_knowledge_domains")


def _url(doc: dict[str, Any]) -> str:
    return f"https://example.com/knowledge/{doc['handle']}"


def _document(doc: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in doc.items() if key != "keywords"} | {
        "url": _url(doc), **PROVENANCE,
    }


def _search(query: str, domain: str | None = None, top: int = 3) -> list[dict[str, Any]]:
    _validate_text(query, "query/question")
    _validate_domain(domain)
    if type(top) is not int or not 1 <= top <= MAX_TOP:
        raise ValueError(f"top must be an integer from 1 to {MAX_TOP}")
    terms = set(term for term in re.findall(r"[a-z0-9-]+", query.lower()) if len(term) > 2)
    hits = []
    for doc in DOCS:
        if domain is not None and doc["domain"] != domain:
            continue
        text = " ".join([doc["domain"], doc["title"], doc["summary"], " ".join(doc["keywords"])]).lower()
        score = sum(text.count(term) for term in terms)
        if score:
            hits.append((score, doc))
    hits.sort(key=lambda hit: (-hit[0], -hit[1]["year"], hit[1]["handle"]))
    return [doc for _, doc in hits[:top]]


PORT = int(os.environ.get("PORT", "8000"))
mcp = FastMCP(
    "custom-chat-app-mock",
    instructions="Read-only fictional demonstration knowledge; example.com citations are illustrative.",
    host="127.0.0.1",
    port=PORT,
    stateless_http=True,
    transport_security=build_transport_security(PORT),
)


@mcp.tool()
def list_knowledge_domains() -> list[str]:
    """List domains in the fictional demonstration fixtures."""
    return list(DOMAINS)


@mcp.tool()
def search_knowledge(query: Query, domain: str | None = None, top: Top = 3) -> dict[str, Any]:
    """Search fictional knowledge; return a documents envelope with provenance, even if empty."""
    return {"documents": [_document(doc) for doc in _search(query, domain, top)], **PROVENANCE}


@mcp.tool()
def get_document(handle: Handle) -> dict[str, Any]:
    """Read a fictional document by its returned handle, or return a mock-labeled not-found result."""
    _validate_text(handle, "handle", 128)
    for doc in DOCS:
        if doc["handle"] == handle:
            return _document(doc)
    return {"error": "No fictional document found for this handle.", **PROVENANCE}


@mcp.tool()
def ask_knowledge(question: Query, domain: str | None = None) -> dict[str, Any]:
    """Return a deterministic fictional answer with fixture citations, not real organizational guidance."""
    docs = _search(question, domain)
    if not docs:
        return {"answer": "No fictional knowledge sources found for this question.", "citations": [], **PROVENANCE}
    return {
        "answer": "Fictional demonstration data — not real organizational guidance. "
        + " ".join(f"{doc['summary']} [{i}]" for i, doc in enumerate(docs, 1)),
        "citations": [{"n": i, **_document(doc)} for i, doc in enumerate(docs, 1)],
        **PROVENANCE,
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
