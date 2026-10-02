# Security boundaries for the custom chat app

## Demo scope

This repository implements a read-only mock with five fictional fixtures about project planning, onboarding, and service operations, with illustrative `example.com` links. Search, document, and answer results identify `source="mock-knowledge"` and `demonstration_data=true`; domain discovery returns a list without that envelope. The UI labels its own demo mode as well. These labels do not establish factual accuracy, access controls, or production readiness for a different endpoint.

The mock has no authentication or user/document authorization. The UI has no user authentication. Cowork packaging checks a local contract, not full platform acceptance. Chat agent files are templates without toolkit lifecycle configuration or referenced icons. Successful local tests or installation cannot establish enterprise permission enforcement. Skill and agent instructions are not server-side security boundaries.

## Network exposure

- The MCP server fixes its listener to `127.0.0.1`, with `PORT` defaulting to 8000. DNS-rebinding protection is **enabled**. Defaults allow exact loopback Hosts with the configured port and corresponding HTTP Origins. IPv6 allowlist entries do not add an IPv6 listener.
- `MCP_ALLOWED_HOSTS` and `MCP_ALLOWED_ORIGINS` are optional comma-separated additions for an approved tunnel. Use exact entries only: host values include the forwarded port when present; origins include the scheme, host, and port when present, without a path. Never use wildcards or disable protection to fix a rejection.
- Malformed additions fail startup without echoing configured values. Public origin additions require HTTPS; HTTP origin additions are loopback-only. The SDK accepts an absent Origin header. These checks do not prove that every client is a browser or approved user.
- Host/origin allowlists are transport checks, **not authentication or authorization**. Do not confuse them with a blanket CORS grant.
- Tunnel **only the fictional MCP mock**, only for a short, approved demonstration. Anonymous access makes it publicly accessible; do not add private data. Stop the tunnel afterward and remove obsolete allowed entries.
- The UI entry point binds to `127.0.0.1:8080` by default, disables proxy-header trust and access logs, and requires an IPv4-loopback peer and exact Host. POST requires the exact same Origin; cross-site Fetch Metadata is rejected. Use the exact IPv4 address, not `localhost`. Framing is blocked and responses are not cached. **Never tunnel the UI, bind it publicly, or share it as production**, even on a different configured port.
- UI browser guards are not authentication. Local software can forge headers and use the process's model identity; per-request limits are not a global rate limiter or usage budget. Do not override the documented entry point with public Uvicorn binding or a proxy.
- The UI permits loopback HTTP MCP by default. Other destinations require an exact approved HTTPS URL matching both `MCP_URL` and `MCP_APPROVED_HTTPS_URL`. URL approval is operator configuration, not a guarantee of server trust. Model and MCP HTTP clients disable environment proxies and automatic redirects; never broaden approval to bypass failures.

## Identity and credentials

The UI uses explicit `AzureCliCredential` for local development, not a fallback credential chain. `USE_MANAGED_IDENTITY=1` selects `ManagedIdentityCredential` for a system-assigned identity on an Azure host that provides one. Enable the host identity and assign least-privilege inference access, such as **Cognitive Services OpenAI User**, on the intended Azure OpenAI resource. This option is not a hosting recipe; selecting it does not add UI sign-in, tenant isolation, or per-user authorization. Normal local testing must leave it unset or `0`.

For Copilot, anonymous authentication (`None`) is allowed here **only for the fictional public mock**. Before any real/production deployment, register supported vault-backed authentication with the Microsoft 365 platform and identity provider (for example OAuth with `OAuthPluginVault`), reference the registration rather than a secret, and enforce authorization on the server for every tool call and document. Authenticate tokens and validate issuer, audience, tenant, and scopes/roles as appropriate; test allowed and denied access with representative users. Client tool pinning and publisher fields cannot enforce these controls. Never switch protected services to anonymous to bypass sign-in errors. Cowork connector configuration and Chat plugin configuration are different surfaces; use their respective platform setup flows. MCP plugin API-key support must not be assumed from API plugin or connector options.

Do not embed credentials in manifests, skills, packages, prompts, screenshots, issues, or logs. Do not print bearer tokens, authorization headers, API keys, credential objects, or credential acquisition traces. The UI trace contains **approved tool names, error status, and demo metadata only**, not arguments/results or credential traces; upstream failures return generic errors. Answer text is not a general-purpose secret/data-loss filter. Do not enable SDK HTTP/debug logging, and redact diagnostics before sharing. If a credential is disclosed, revoke or rotate it and remove exposed copies; deleting a file alone does not invalidate a credential.

## Inputs, outputs, and tool trust

- Use only fictional, nonsensitive questions and drafts. Do not upload or send personal, internal, confidential, regulated, or sensitivity-labeled documents to this demo.
- Prompts and tool results may be sent to the configured Azure OpenAI service and, for optional integrations, processed by Microsoft 365. Obtain organizational approval for any use beyond fictional testing.
- The UI advertises and invokes only discovered instances of `list_knowledge_domains`, `search_knowledge`, `get_document`, and `ask_knowledge`, using local schemas and validating each entire call batch before execution. Chat plugin templates pin those four tools explicitly. Names and schemas do not prove another server is read-only; review its behavior before use.
- The mock validates nonblank query/question/handle values, exact known domains, and integer result bounds. It implements no write tools, external retrieval, or enterprise authorization. The UI additionally bounds messages, request bodies, arguments, tool/model rounds, results, and deadlines; see its [guide](chat-ui/README.md) for exact limits. Neither component implements authenticated ingress or comprehensive abuse protection.
- Treat retrieved text as untrusted evidence, never as instructions to reveal secrets, invoke other tools, browse unrelated links, or change security settings.
- Preserve citations as returned; `example.com` links are illustrative, not verified publications. Report missing evidence instead of inventing it.
- Drafting a briefing or email does not authorize sending, publishing, overwriting, or saving a file. Confirm user intent and permissions for separate actions.

## Before any production redesign

Add authenticated ingress, server-side authorization, tenant/user isolation, endpoint validation, appropriate network controls, rate limits, usage budgets, safe logging, dependency maintenance, and retention/privacy controls. Review source rights and select a license before distribution. Validate denial paths and injection resistance. None of this is established by a successful mock call or package installation.

## Before publication or sharing

- Scan source, staged changes, Git history, local configuration, generated manifests, and final archives with an approved secret scanner. Inspect endpoints, app/tenant/resource identifiers, publisher metadata, logs, and screenshots for private configuration. Run scans locally with redacted output; never paste matching secret values into issues or chat.
- [.gitignore](.gitignore) excludes local environment files (except reviewed examples), virtual environments, caches, local MCP configuration, and build/distribution output. Ignore rules do not remove already tracked files, sanitize archives, revoke secrets, or guarantee a clean repository. Blank [appPackage/.env.example](appPackage/.env.example) is an inventory only, not an auto-loaded environment or permission to commit filled values.
- Rebuild and inspect each package after endpoint/tool/configuration changes. Unresolved placeholders, stale artifacts, omitted icons, and successful JSON parsing are not a validated upload. The Cowork packager performs no endpoint or deployment verification; the Chat templates have no root lifecycle. Review generated binaries/archives separately even when ignored.
- Confirm publisher consent, contributor/dependency/source rights, privacy/terms, tenant approval, and the user's chosen license before distribution. No license, ownership, third-party affiliation, security certification, or scan guarantee is assigned by this repository.

## Reporting a concern

No dedicated security contact or supported-version policy is established by this repository documentation. Use the repository host's private vulnerability-reporting channel **if enabled**, or an established private contact with the repository maintainer. Do not publish secrets, private document content, or exploitable endpoint details in a public issue. If no private channel is available, first request a private reporting method without disclosing sensitive details.

Include the affected component, sanitized reproduction steps, expected versus observed behavior, and impact. No response time or remediation guarantee is implied.

## References

Identity and authentication guidance checked on October 2, 2026:

- [Azure OpenAI identity guidance](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/managed-identity)
- [AzureCliCredential](https://learn.microsoft.com/en-us/python/api/azure-identity/azure.identity.azureclicredential?view=azure-python)
- [Microsoft 365 MCP/API plugin authentication](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/plugin-authentication)