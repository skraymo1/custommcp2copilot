# Custom chat app: mock MCP server

A read-only Streamable HTTP mock for fictional project planning, onboarding, and service operations. It is not a live knowledge service, a production search system, or an authorization implementation. Source URLs use `example.com` and are illustrative, not published evidence.

The implementation in [server.py](server.py) exposes exactly the four tools below. [test_client.py](test_client.py) checks discovery and execution against this mock contract. Other folders are separate integrations and may still need alignment; a passing server test does not prove those integrations work.

## Tools

| Signature | Use |
| --- | --- |
| `list_knowledge_domains()` | Discover valid domain values |
| `search_knowledge(query, domain=None, top=3)` | Search fictional fixtures; default is three results |
| `get_document(handle)` | Read a document using a handle returned by search |
| `ask_knowledge(question, domain=None)` | Obtain a mock synthesized answer and citations |

All tools are read-only. Search accepts only `query`, optional `domain`, and optional `top`; there are no geography, persona, or year filter parameters. Use returned domains and handles rather than guessing. Mock result metadata is `source="mock-knowledge"` and `demonstration_data=true`. A no-match result is an evidence gap, not an invitation to invent a source.

### Results and input limits

- `list_knowledge_domains()` returns a **list**: `onboarding`, `project-planning`, and `service-operations`. It is not a provenance envelope.
- `search_knowledge()` returns an object with `documents`, `source`, and `demonstration_data`. Each document also carries provenance, `handle`, `title`, `year`, `domain`, `summary`, and an illustrative HTTPS `example.com` URL. No matches means `documents=[]` with the same provenance, not a bare empty list.
- `get_document()` returns the same document fields. An unknown handle returns `error` and mock provenance, without an invented URL.
- `ask_knowledge()` returns `answer`, `citations`, and mock provenance. Citations preserve document fields and add the numbered reference `n`. No matches returns an explicit evidence-gap answer and `citations=[]` with provenance.
- `query` and `question` must be nonblank strings of **1–1000 characters**. `top` is a strict integer from **1–10**, default **3**; booleans and numeric strings are rejected. Handles must be nonblank strings of **1–128 characters**. Invalid inputs raise MCP tool errors rather than being silently truncated.
- `domain` is optional; when supplied it must be an exact returned domain. Unknown or empty domains are input errors. An accepted query can still yield no evidence within a valid domain.

Search is deterministic keyword matching over five invented fixtures, not semantic search or external retrieval. It defaults to at most three documents; answers use at most three sources. Years are fictional fixture metadata, not publication claims.

## Run locally

Requires **Python 3.11 or later** and **MCP SDK 1.27 or later, below 2**. The minimum SDK is set to the version used to validate schemas and transport behavior. From the repository root in PowerShell:

```powershell
cd mock-mcp-server
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe server.py
```

Select a newer installed Python version instead of `-3.11` if appropriate. Keep the terminal open. The server always binds to `127.0.0.1`; `HOST` does not override this. Optional `PORT` selects an integer from 1–65535 (default 8000). The default endpoint is `http://127.0.0.1:8000/mcp`.

In a second PowerShell terminal, from the repository root:

```powershell
cd mock-mcp-server
.\.venv\Scripts\python.exe test_client.py
```

The client checks exactly four discovered tools, successful calls, mock provenance, citation/document consistency, and all three no-result paths. Every tool invocation has a 30-second timeout. Stop the server with **Ctrl+C** when finished.

### Automated regression tests

From the repository root, after installing the server requirements:

```powershell
.\mock-mcp-server\.venv\Scripts\python.exe -m compileall -q mock-mcp-server
.\mock-mcp-server\.venv\Scripts\python.exe -m unittest discover -s mock-mcp-server -p test_server.py -v
```

[test_server.py](test_server.py) tests the four-tool contract, fixture provenance, missing evidence, input limits, schema constraints, and transport settings. Tests use the actual MCP SDK (no fake fallback), exercise its Host/Origin middleware, and start/stop a temporary loopback HTTP server for the complete smoke workflow and HTTP 421/403 rejection paths. No running server, model service, credentials, or tunnel is required. Public tunnel forwarding and remote client integration need separate approved end-to-end tests.

Example manual sequence:

1. Call `list_knowledge_domains()`.
2. Call `search_knowledge(query="onboarding", top=3)`; supply `domain` only if needed, using a returned value.
3. Call `get_document(handle=...)` with a returned handle.
4. Call `ask_knowledge(question="Summarize the fictional onboarding guidance.")`.
5. Confirm the results are demonstration data and the answer's citations match the returned sources.

For model-driven testing, see [../chat-ui/README.md](../chat-ui/README.md). The local UI is not required to run this server.

## Optional HTTPS tunnel for Copilot

Remote Copilot cannot reach your computer's loopback URL. Use an organization-approved HTTPS tunnel **only for the fictional public mock**, never for the unauthenticated chat UI or real/private knowledge.

DNS-rebinding protection is **enabled**. Default allowed Hosts are exactly `127.0.0.1:PORT`, `localhost:PORT`, and `[::1]:PORT`; default allowed Origins are their `http://` equivalents. No wildcard ports or domains are allowed. IPv6 Host validation does not add an IPv6 listener. Optional environment variables are:

| Variable | Format |
| --- | --- |
| `MCP_ALLOWED_HOSTS` | Comma-separated exact tunnel Host entries, including a port if forwarded |
| `MCP_ALLOWED_ORIGINS` | Comma-separated exact HTTPS tunnel origins: scheme, host, optional port; no path (even `/`) |

They add approved tunnel entries to the loopback configuration; they do not authorize users or grant CORS access. Use the actual forwarded Host/Origin values from your approved tunnel configuration, including a port only when present in that header. Values are exact: `demo.example.com` and `demo.example.com:443` are distinct entries. Outer whitespace is trimmed and duplicates removed. Blank settings add nothing. Malformed hosts, wildcards, credentials, paths, query strings, fragments, invalid ports, and empty items in nonempty comma-separated lists cause startup to fail closed. Extra `http://` origins are allowed only for exact loopback names/IPs; public origins must use HTTPS. An absent Origin header is accepted by the SDK and does not justify adding unrelated origins.

Once an approved tunnel is allocated, set the actual entries in the **server terminal** and restart the server:

```powershell
$env:MCP_ALLOWED_HOSTS = Read-Host 'Exact forwarded tunnel Host entry (include port if present)'
$env:MCP_ALLOWED_ORIGINS = Read-Host 'Exact approved tunnel origin (scheme, host, optional port; no path)'
.\.venv\Scripts\python.exe server.py
```

Keep the tunnel forwarding to local **HTTP** on the configured port; public HTTPS is terminated by the relay. If requests are rejected, correct exact allowlist entries rather than disabling rebinding protection. Verify both discovery and execution at the public endpoint:

```powershell
$mcpUrl = Read-Host 'Complete approved HTTPS mock endpoint, including /mcp'
.\.venv\Scripts\python.exe test_client.py $mcpUrl
```

See [../cowork-plugin/README.md](../cowork-plugin/README.md) for packaging. If the tunnel changes, update allowed entries, restart, rebuild affected packages, and retest. Stop the tunnel after the demonstration. Do not substitute a real service URL and assume the same authentication, schemas, or permissions apply.

## Troubleshooting and safety

- Connection failure: check the server is running and the URL ends with the correct MCP path.
- Unexpected tools: verify the endpoint runs this mock, not another service or a stale process.
- Rebinding/Origin rejection: verify exact forwarded values; leave protection enabled.
- Tunnel 502: verify local port 8000 and HTTP forwarding, not local HTTPS.
- No results: narrow the fictional query; do not present external knowledge as fixture evidence.

**Public demo mock only — no secrets or private data.** This server has no authentication or enterprise authorization. Anyone who reaches an approved public tunnel can call it; Host/Origin allowlists are not user access controls. Use only fictional, nonsensitive inputs, never add internal documents, and stop the tunnel/server after the demonstration. Never expose the unauthenticated chat UI. A real service requires a separate authentication, authorization, rate-limit, logging, and data-handling design.

Read [../SECURITY.md](../SECURITY.md) before exposure. Source rights and a repository license are not assigned by this demo; the user must choose a license and verify redistribution rights.
