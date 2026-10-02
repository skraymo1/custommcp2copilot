# Custom chat app: local visual test harness

An optional, unauthenticated **loopback-only** chat demo. An Azure OpenAI deployment receives allowlisted MCP tools as functions; the page shows the answer and mock tool activity so a tester can inspect grounding. It is not Copilot, does not install an agent, and does not prove delegated identity or server authorization.

The implementation in [app.py](app.py) validates configuration at startup, uses explicit credentials, advertises and invokes only the four approved tools, and redacts tool activity. This is a public **source-code demonstration**, not a publicly hosted UI or production security boundary.

**Do not expose this UI through a tunnel, on a public interface, or as shared production.** Its Azure identity authenticates model calls, not users of the web page. Use only fictional, nonsensitive prompts. Prompts and tool results may be processed by Azure OpenAI.

## Prerequisites

- Python **3.11 or later**.
- The aligned [mock server](../mock-mcp-server/README.md) running on `127.0.0.1:8000`.
- Your existing Azure OpenAI endpoint and an actual deployment that supports chat tool calling. The deployment name can differ from its model name; these docs assign neither a model nor a resource.
- Azure CLI installed and signed in to the correct tenant/account using your organization's approved process. The local credential is **`AzureCliCredential`**, not `DefaultAzureCredential`.
- Least-privilege inference access, such as **Cognitive Services OpenAI User**, on the Azure OpenAI resource for the identity used by the app. Role changes may take time to propagate.

## Environment contract

| Variable | Required/default | Meaning |
| --- | --- | --- |
| `AZURE_OPENAI_ENDPOINT` | Required; no fallback | Your Azure OpenAI resource endpoint |
| `AZURE_OPENAI_DEPLOYMENT` | Required; no fallback | Your existing tool-capable deployment name |
| `AZURE_OPENAI_API_VERSION` | Optional; `2024-10-21` | Versioned Chat Completions API contract; verify compatibility with your deployment |
| `MCP_URL` | Optional; `http://127.0.0.1:8000/mcp` | Loopback HTTP mock MCP endpoint by default |
| `MCP_APPROVED_HTTPS_URL` | Unset by default | Exact approved HTTPS URL; must match `MCP_URL` to permit a non-loopback-HTTP destination |
| `USE_MANAGED_IDENTITY` | Unset by default | Set to exactly `1` only on an Azure host that provides managed identity |
| `PORT` | Optional; `8080` | UI port; binding remains loopback |

There is **no dotenv auto-loading**. Set variables in the launching shell or approved host configuration. A dotenv file alone does not configure the Python UI. Do not commit local values or credentials.

`USE_MANAGED_IDENTITY=1` is a credential-selection option for a future hosting design, not a deployment recipe. Enable the host's identity and grant it inference access before using it. Do not enable it for normal local testing, even on an Azure-backed development machine. Managed identity does not make this unauthenticated UI safe to share; hosting requires a separate security redesign.

## Run locally

Start the mock using its guide in one terminal. In a second PowerShell terminal, from the repository root:

```powershell
cd chat-ui
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:AZURE_OPENAI_ENDPOINT = Read-Host 'Your actual Azure OpenAI resource endpoint'
$env:AZURE_OPENAI_DEPLOYMENT = Read-Host 'Your actual chat tool-calling deployment name'
$env:AZURE_OPENAI_API_VERSION = '2024-10-21'
$env:MCP_URL = 'http://127.0.0.1:8000/mcp'
Remove-Item Env:USE_MANAGED_IDENTITY -ErrorAction SilentlyContinue
$env:PORT = '8080'
.\.venv\Scripts\python.exe app.py
```

Choose a newer installed Python version if necessary. Open `http://127.0.0.1:8080` and ask:

> Using the custom chat app's mock knowledge, summarize the fictional project planning guidance. Cite only returned sources and identify evidence gaps.

The model is advertised **only** discovered instances of `list_knowledge_domains`, `search_knowledge`, `get_document`, and `ask_knowledge`. Local schemas forbid unexpected fields, wrong types, blank strings, oversized arguments, and out-of-range `top` values. Invocation rejects unknown or undiscovered tools; each batch is validated before any call in it executes. Server-provided descriptions and schemas are not forwarded. Connecting another MCP service does not authorize sending it data or prove it is read-only merely because names match.

## Local browser and execution protections

- Launch with the documented Python entry point, which fixes the listener to `127.0.0.1`, disables proxy-header trust and access logs, and avoids verbose server diagnostics. Do not use a separate Uvicorn launch command, proxy, or tunnel to override this design.
- Open the exact address `http://127.0.0.1:<PORT>`, not `localhost`. Requests require the exact configured Host and an IPv4-loopback peer. All POST requests require the exact matching Origin; missing, duplicate, `null`, or foreign origins are rejected. Cross-site Fetch Metadata is also rejected. No CORS middleware or cross-origin preflight permission is provided.
- Frames are blocked; responses are not cached. These controls mitigate browser local-service abuse and DNS rebinding. They are **not user authentication** and do not protect against malicious local software that can forge headers, an approved same-origin page, or an administrator who changes the code or puts a proxy in front of it.
- Messages are limited to 2,000 nonblank characters, JSON request bodies to 16,384 bytes, and body receipt to five seconds. Unknown request fields are rejected without echoing their values.
- Each request executes at most **three tool rounds**, **eight tool calls**, and **four model completions** (the last may provide an answer, but cannot execute more tools). Tool arguments are capped at 4,096 UTF-8 bytes and validated against local schemas; query/question limits are 1,000 characters, handles 128, and `top` 1–10. Tool results and model answers are capped at 16,000 characters.
- The asynchronous demo operation has a 60-second deadline, upstream HTTP timeouts are 20 seconds, and model retries are disabled. This is a per-request limit, not a global rate limiter or a guarantee of instantaneous cancellation of synchronous SDK credential work.
- Errors return generic messages, never upstream exception text, configured endpoints, deployment names, tokens, or full validation diagnostics. Tool-level error text is replaced before sending it to the model. Do not enable SDK HTTP/debug logging for this demo.
- Activity traces contain **only** approved tool names, an error boolean, and `demonstration_data=true`; no arguments, results, model/resource identifiers, or URLs. Answer citations may contain fictional URLs returned by tools; the answer itself is not a general-purpose data-loss-prevention filter. Demo metadata labels this UI's mode, not independently verified provenance of an external server.

## Optional approved external MCP destination

Prefer the local fictional mock. If an authorized tester needs an external **fictional, nonsensitive** demo server, set both `MCP_URL` and `MCP_APPROVED_HTTPS_URL` to the **same exact HTTPS URL**, including the path. For example, an illustrative (not running) endpoint would be `https://example.com/mcp`. HTTP external endpoints, URL credentials, query strings, fragments, wildcards, and mismatched approvals are rejected. Approval is operator configuration, never a value supplied by a chat message. Review the endpoint, operator, data handling, and tool behavior first; exact URL approval is not authorization or authentication.

Both MCP and model HTTP clients disable environment proxies and automatic redirects. An approved server that redirects is not followed; set the explicitly approved final HTTPS URL instead. The connector has no external-service authentication setup. Real enterprise access requires a separate server/client authorization design. **External MCP approval never changes the UI's loopback binding or same-origin policy. Do not tunnel the UI.**

## What a passing demo looks like

- Actual successful mock tool calls appear in the activity trace; a generated answer alone is insufficient.
- Mock results identify `source="mock-knowledge"` and `demonstration_data=true`.
- Citations preserve returned titles, handles, and `example.com` URLs. The answer explicitly labels findings as **fictional demonstration data**, not real policy or research.
- No-result or tool-error cases are reported honestly, not replaced with invented evidence.
- Traces show approved tool names, error status, and demo metadata only. Full evidence is processed by the model, not displayed as a raw trace. A completed tool call is an activity signal, not proof the model's answer is correct.

Stop the UI with **Ctrl+C** after testing. This demo can incur model usage charges.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Missing endpoint/deployment | Set both required variables in the process's launching shell; there are no private defaults |
| Credential failure | Check Azure CLI installation, signed-in account/tenant, and that local managed identity selection is unset |
| 401/403 | Verify identity, resource inference role, and resource network access; do not paste tokens into diagnostics |
| 404 | Verify endpoint and exact deployment name, not an assumed model name |
| API/tool-calling rejection | Verify deployment compatibility with the configured API version and request options; no universal model-specific setting is promised |
| MCP connection failure | Test the mock separately; use the explicit IPv4 endpoint if localhost resolves to IPv6 |
| Local access rejected (403) | Open the exact IPv4 address and configured port; POST must carry the matching Origin. Do not add CORS or proxy-header exceptions |
| Generic demo failure (502) | Check your configuration, identity permissions, deployment/API compatibility, and mock independently; upstream diagnostics are intentionally not exposed |
| Execution limit reached | Simplify the fictional question; the demo does not execute unlimited tool batches |
| Answer without mock calls | Treat as an ungrounded result, not a successful integration |

## Mocked validation

From the repository root, after installing [requirements.txt](requirements.txt), run `python -m unittest discover -s chat-ui -p test_app.py -v` using the same interpreter as the UI. [test_app.py](test_app.py) covers configuration and URL approval, explicit credential selection, discovery/invocation allowlisting, argument validation, Host/Origin/peer checks, body/message bounds, tool round/call limits, deadlines, sanitized errors, and trace redaction. All Azure model, credential acquisition, and MCP interactions are mocked: tests make **no live Azure calls** and do not require credentials.

Mocked tests do not verify real Azure RBAC/network access, model/API compatibility, external MCP authorization, browser behavior end to end, or the correctness of model grounding. Requirements specify key compatibility floors, not a fully locked production supply chain.

## References and rights

Azure guidance checked against Microsoft Learn on October 2, 2026:

- [Azure OpenAI Microsoft Entra ID and managed identities](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/managed-identity)
- [AzureCliCredential](https://learn.microsoft.com/en-us/python/api/azure-identity/azure.identity.azureclicredential?view=azure-python)
- [Local developer accounts and explicit tool credentials](https://learn.microsoft.com/en-us/azure/developer/python/sdk/authentication/local-development-dev-accounts)
- [System-assigned managed identity for Python](https://learn.microsoft.com/en-us/azure/developer/python/sdk/authentication/system-assigned-managed-identity)
- [Versioned Azure OpenAI keyless connections and token scope](https://learn.microsoft.com/en-us/azure/developer/ai/keyless-connections)

Those pages confirm explicit Azure CLI credentials for local development and managed identity for Azure-hosted access. This app uses the versioned Azure OpenAI client with the Cognitive Services token scope; v1 API examples do not override that contract. Managed identity selection is explicit (`USE_MANAGED_IDENTITY=1`) and uses a system-assigned identity, with no credential-chain fallback. Read [../SECURITY.md](../SECURITY.md). No source license or ownership is assigned here; the user must choose a license and verify source rights before redistribution.
