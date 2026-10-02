# Custom chat app: mock knowledge via MCP

A demonstration of read-only Model Context Protocol (MCP) tools consumed by a local custom chat app and optional Microsoft 365 Copilot integrations. The knowledge fixtures cover **fictional project planning, onboarding, and service operations**, not real organizational research or policy. Source links on `example.com` are illustrative citations, not evidence of published documents.

The server, local UI, Cowork plugin, and Chat agent templates use the same four approved tools. The server contains five invented fixtures and deterministic keyword matching, not external retrieval. Local implementation and offline tests do not establish live model grounding, tenant installation, production authorization, or package acceptance.

## Components

| Component | Purpose | Guide |
| --- | --- | --- |
| Mock MCP server | Read-only fictional knowledge over Streamable HTTP | [mock-mcp-server/README.md](mock-mcp-server/README.md) |
| Local custom chat app | Azure OpenAI tool-calling test harness with mock tool activity | [chat-ui/README.md](chat-ui/README.md) |
| Cowork plugin | Knowledge research and briefing skills plus a remote connector | [cowork-plugin/README.md](cowork-plugin/README.md) |
| Optional Copilot Chat agent | Declarative agent and MCP plugin templates, not a complete toolkit project | [appPackage/manifest.json](appPackage/manifest.json) |

The local path is: question → custom chat app → Azure OpenAI → allowlisted MCP tool → fictional result → cited demo answer. Cowork and Copilot Chat are separate consumers of the MCP server; neither uses or requires the local chat UI. Installing one package does not install the other integration.

## Tool contract

All four tools are read-only:

| Tool signature | Purpose |
| --- | --- |
| `list_knowledge_domains()` | Discover domain values supported by the fixtures |
| `search_knowledge(query, domain=None, top=3)` | Find matching fictional documents; default result count is three |
| `get_document(handle)` | Retrieve a fictional document using a returned handle |
| `ask_knowledge(question, domain=None)` | Return a mock answer with fixture citations |

`list_knowledge_domains()` returns a list, not a provenance envelope. Search returns `documents`; document lookup returns a document or a not-found `error`; answers return `answer` and `citations`. Those three result types identify `source="mock-knowledge"` and `demonstration_data=true`, including no-result responses. Domains and handles must come from tool results. Queries/questions are nonblank and at most 1000 characters, handles at most 128, and `top` a strict integer from 1–10. No unsupported geography, year, or persona filters, uploads, writes, email-send, or enterprise authorization tools are provided.

## Local demonstration

1. Use **Python 3.11 or later** and follow the [server guide](mock-mcp-server/README.md) to start the mock on `127.0.0.1:8000`, with MCP at `http://127.0.0.1:8000/mcp`.
2. Run the server guide's discovery/call smoke test to verify exactly four tools, mock provenance, citation consistency, and no-result behavior. Its regression tests also exercise input validation and Host/Origin rejection.
3. For the optional UI, follow the [chat app guide](chat-ui/README.md). Supply your actual Azure OpenAI endpoint and deployment name through environment variables and use the signed-in Azure CLI identity locally.
4. Open `http://127.0.0.1:8080` and ask: **Using the custom chat app's mock knowledge, summarize the fictional onboarding guidance. Include returned sources and evidence gaps.**
5. Confirm a successful tool call, returned citations, and the demonstration-data label. A fluent answer without tool evidence is not a pass.

The UI has **no user authentication**. Its entry point binds to IPv4 loopback and its middleware enforces the exact Host, peer, and same Origin for POST requests. It validates tool invocation as well as discovery, bounds execution, and shows only tool names/status in activity traces. These controls are not user access control or proof of answer correctness. **Do not tunnel port 8080 or expose it as shared production.** Prompts and tool evidence are sent to the configured model service; use only fictional, nonsensitive inputs. See [SECURITY.md](SECURITY.md).

## Optional Microsoft 365 integrations

Cowork needs a reachable HTTPS MCP endpoint, Cowork access, tenant permission, and a separately prepared plugin package. See the [Cowork guide](cowork-plugin/README.md) for its implemented six-parameter packaging contract, generated demo icons, offline tests, validation limits, and installation route. The packager does not contact an endpoint, register an app, or deploy anything. It packages the two skills and connector, not the Chat agent or local UI.

For Copilot Chat, [appPackage/manifest.json](appPackage/manifest.json), [appPackage/declarativeAgent.json](appPackage/declarativeAgent.json), [appPackage/ai-plugin.json](appPackage/ai-plugin.json), and [appPackage/instruction.txt](appPackage/instruction.txt) are source integration templates. The plugin uses namespace `customchatapp` with four explicit `functions`, inline MCP definitions, and the same four names in `run_for_functions`, not a wildcard. The pinned definitions mirror the mock's input contract; refresh them against actual `tools/list` output before packaging or after a server change. Do not infer automatic approval or safe-execution annotations from these templates.

**This is not a deployable Chat agent project as-is.** There is no toolkit YAML build/lifecycle configuration in the repository. The manifest's color and outline icons are missing from [appPackage](appPackage); root icons are also absent. Stale generated JSON content has been cleared; only empty ignored files remain in [appPackage/build](appPackage/build), not a ready package. No scaffolding or icons are generated by this cleanup. To enable this optional route separately:

1. Follow the [Microsoft Learn MCP walkthrough](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/build-mcp-plugins) in a separately configured Microsoft 365 Agents Toolkit project. The current guide requires Toolkit 6.12.0 or later plus the stated account/access prerequisites. Supply the missing lifecycle/build configuration and referenced icons, or integrate these templates into that project; there is no root Provision/debug workflow here.
2. Use [appPackage/.env.example](appPackage/.env.example) as a **blank configuration inventory**, not an auto-loaded root environment. Map `TEAMS_APP_ID`, `APP_NAME_SUFFIX`, `MCP_URL`, `PUBLISHER_NAME`, `PUBLISHER_EMAIL`, `PUBLISHER_WEBSITE_URL`, `PUBLISHER_PRIVACY_URL`, and `PUBLISHER_TERMS_URL` through the chosen packaging lifecycle. Use your actual stable app ID and authorized publisher/legal metadata; no identity or affiliation is assigned here. `APP_NAME_SUFFIX` may be empty. Resolve `${{...}}` variables and the instruction file reference during packaging; do not commit local values or upload unresolved templates. The Python UI does not load dotenv files.
3. For an approved remote demo, expose **only the fictional MCP mock**, not the UI. Use a complete HTTPS MCP URL (normally ending in `/mcp`), exact server Host/Origin additions, and enabled rebinding protection per the [server guide](mock-mcp-server/README.md). Discovery uses MCP `tools/list` over Streamable HTTP, not a separate `/discover` route.
4. Rebuild, inspect, and validate the **Chat agent package** against current schemas and tenant policy before sideloading or publishing. Check resolved metadata, four pinned tools, instructions, icons, HTTPS endpoint, and mock-only anonymous settings. Rebuild after configuration, endpoint, or tool changes. Source JSON parsing and a local UI demonstration do not prove platform acceptance.

Anonymous authentication (`None`) is permitted here **only for the fictional public mock**. Anyone reaching an approved tunnel can call it. Stop the tunnel afterward. A real/production service requires supported platform-registered, vault-backed authentication (for example OAuth with `OAuthPluginVault` and a registration reference) and server-side authorization for every tool/document. Never put secrets in manifests or substitute a protected endpoint while retaining `None`. MCP plugin authentication and Cowork connector authorization are different configuration surfaces; use their respective flows, not a copied auth block.

Cowork skills are not automatically loaded into the Chat agent. The local UI does not prove Copilot installation, delegated identity, or authorization. No Azure model/resource ID, app ID, or secret is assigned by these docs. Before sharing, review [SECURITY.md](SECURITY.md), scan source, history, and final archives for secrets/private configuration, and verify source rights. Ignore rules are not a secret scanner and do not remove already tracked material.

## Rights and license

This documentation does **not** assign a source license or assert ownership of the repository or fixtures. The user must choose an appropriate license and verify source rights, contributor permissions, dependencies, branding, and redistribution terms before sharing. Fictional data and `example.com` citations do not grant rights to unrelated real source material.

## Verified guidance

Azure identity and Copilot guidance checked against Microsoft Learn on October 2, 2026:

- [Azure OpenAI Microsoft Entra ID and managed identities](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/managed-identity)
- [AzureCliCredential for Python](https://learn.microsoft.com/en-us/python/api/azure-identity/azure.identity.azureclicredential?view=azure-python)
- [Build MCP plugins for declarative agents](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/build-mcp-plugins)
- [Pinned tools versus dynamic discovery](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/plugin-dynamic-tool-discovery)
- [Plugin manifest schema 2.4](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/plugin-manifest-2.4)
- [Build Cowork plugins](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development)
- [Configure MCP and API plugin authentication](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/plugin-authentication)

Tenant rollout, UI labels, and supported packaging/authentication options can change. Recheck the relevant Learn guide before deployment.
