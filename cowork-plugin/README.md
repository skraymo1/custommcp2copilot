# Custom chat app: knowledge plugin for Copilot Cowork

A demo plugin for **fictional project planning, onboarding, and service operations**. It packages two read-only skills and one remote connector, not a server, model, or local UI. Findings and draft text are demonstration data, not real organizational guidance. Only this folder's packaging implementation is covered here; other integrations have separate configuration and validation.

## Skills and connector contract

- [skills/knowledge-research/SKILL.md](skills/knowledge-research/SKILL.md): cited answers, fictional document lookup, and evidence gaps.
- [skills/knowledge-briefing/SKILL.md](skills/knowledge-briefing/SKILL.md): cited briefs, slide outlines, email drafts, and optional comparison of fictional text supplied in chat. **Draft text only; no files written or emails sent.**
- Connector ID/namespace: `custom-chat-app-knowledge`, displayed as **Custom chat app mock knowledge**. Discovery may qualify tool names with this connector; match the underlying names and schemas, not an unrelated connector.

| Read-only tool | Contract |
| --- | --- |
| `list_knowledge_domains()` | Returns a domain list, possibly in an MCP `result` wrapper; no provenance envelope |
| `search_knowledge(query, domain=None, top=3)` | Returns `documents`, `source`, and `demonstration_data` |
| `get_document(handle)` | Returns a document or a not-found `error`, with mock provenance |
| `ask_knowledge(question, domain=None)` | Returns `answer`, `citations`, and mock provenance |

Evidence identifies `source="mock-knowledge"` and `demonstration_data=true`. Source URLs on `example.com` and fixture years are illustrative, not verified publications. Queries/questions are nonblank and at most 1000 characters; handles are nonblank and at most 128; `top` is an integer from 1–10 (default 3). Use domains and handles returned by tools. Do not send unsupported geography, year, or persona filters. No results means an evidence gap, not permission to invent citations.

**Only fictional, nonsensitive inputs.** No personal, internal, confidential, regulated, or sensitivity-labeled data or excerpts, even with user consent. Skills do not read personal storage, workspace files, or attachments. They do not upload, write, save, overwrite, send, publish, share, or change a service. Retrieved text is untrusted evidence, never tool instructions. Skill instructions are not a server-side security boundary.

## Prepare the fictional mock endpoint

1. Start and verify the [mock server](../mock-mcp-server/README.md), using Python 3.11 or later, normally at `127.0.0.1:8000`. Verify all four schemas and successful evidence calls locally.
2. If remote Cowork testing is approved, allocate an HTTPS tunnel to **MCP port 8000 only**. Remote Cowork cannot reach your computer's loopback address. Forward to local HTTP; the relay terminates public HTTPS.
3. Configure the mock's exact `MCP_ALLOWED_HOSTS` and `MCP_ALLOWED_ORIGINS` entries per its guide, restart, and verify discovery and execution through the complete public MCP URL. Leave DNS-rebinding protection enabled; never use wildcards or disable it to bypass rejection.
4. Review the endpoint and its operator. This template uses `authorization.type="None"` **only for the fictional public mock**. Anyone reaching the tunnel can call it. Keep it open only for the approved demonstration and stop the tunnel and server afterward.

**Never tunnel the unauthenticated UI on port 8080.** The [local UI](../chat-ui/README.md) is an optional test harness, not this plugin's backend. A URL passing packaging validation does not prove approval, reachability, fictional content, transport security, or authorization.

## Package on Windows

Requires Windows PowerShell 5.1 or PowerShell 7 on Windows, with System.Drawing available. [package.ps1](package.ps1) requires **exactly these six application parameters**, with no defaults:

| Parameter | Value and source template slot |
| --- | --- |
| `McpUrl` | Complete approved HTTPS fictional mock endpoint including its MCP path; `{{McpUrl}}` |
| `AppId` | Your nonzero GUID in hyphenated D format, stable for updates; `{{AppId}}` |
| `PublisherName` | Your authorized publisher name, 1–32 characters; `{{PublisherName}}` |
| `WebsiteUrl` | Your actual publisher website; `{{WebsiteUrl}}` |
| `PrivacyUrl` | Your actual applicable privacy notice; `{{PrivacyUrl}}` |
| `TermsOfUseUrl` | Your actual applicable terms; `{{TermsOfUseUrl}}` |

From the repository root:

```powershell
cd cowork-plugin
$mcpUrl = Read-Host 'Complete approved HTTPS fictional mock endpoint'
$appId = Read-Host 'Your valid stable package GUID'
$publisherName = Read-Host 'Your authorized publisher name (1-32 characters)'
$websiteUrl = Read-Host 'Your actual publisher website URL'
$privacyUrl = Read-Host 'Your actual applicable privacy notice URL'
$termsOfUseUrl = Read-Host 'Your actual applicable terms URL'
.\package.ps1 -McpUrl $mcpUrl -AppId $appId -PublisherName $publisherName -WebsiteUrl $websiteUrl -PrivacyUrl $privacyUrl -TermsOfUseUrl $termsOfUseUrl
```

The script parses [manifest.json](manifest.json) as JSON, checks the six template slots, assigns only the intended properties, and serializes a generated copy. **No regex/text substitution** is used. The source template remains unchanged and is not uploadable as-is. No model deployment or API key is required. Use your actual authorized metadata for distribution, not the throwaway GUID and `example.com` URLs used in offline tests. Packaging does not contact an endpoint, register an app, or deploy anything.

Output: [dist/custom-chat-app.zip](dist/custom-chat-app.zip), ignored by Git. Its root contains [dist/build/manifest.json](dist/build/manifest.json), generated generic **C** icons (192×192 color PNG, 32×32 white-on-transparent outline PNG), and the two renamed skill folders. Source icons and unreferenced skill folders are deliberately not copied. Only each referenced skill's instruction file is packaged; companion files would require a separate contract extension. Generic icons are demonstration branding, not a store-submission approval.

### Local validation contract

Before touching generated output, the script rejects:

- Missing/empty parameters, whitespace-only publisher names, names over 32 characters, surrounding whitespace or control characters; invalid/all-zero/non-D-format GUIDs.
- Any of the four URLs that is not absolute HTTPS with an exact host and valid port, or contains credentials (including empty userinfo), whitespace/control characters, backslashes, query strings or fragments (even empty `?`/`#`), wildcards or encoded hosts.
- Unresolved placeholders in supplied values, generated JSON, or skill text: double braces, `${...}`, `$[...]`, angle-bracket slots, double-underscore slots, `YOUR-`/`YOUR_`/`YOUR `, `REPLACE_ME` variants, and `PLACEHOLDER`, case-insensitively and after percent decoding. These forms are reserved, not literal publisher/URL text.
- A source manifest without the exact six documented slots, a connector other than the one generic ID, or nonmock auth settings. This packager supports only `None` without `referenceId`, not production credentials.
- Missing, duplicate, unexpected, or linked skill folders/instruction files. Exactly the two listed folder paths must exist. Each instruction file must have one frontmatter block with the exact matching `name` and a nonblank plain (starting with an alphanumeric character) or block `description`.
- Icon references other than the two generated names.

This is **local contract validation, not full Microsoft schema/portal validation**. Rebuilds replace generated staging/output on success. A rejected preflight leaves prior output unchanged; never mistake an old ZIP for a successful new build. Inspect the archive after every successful build: root layout, resolved publisher fields and endpoint, skill references, icons, generic branding, and mock-only anonymous settings. Rebuild/update when a tunnel or publisher configuration changes.

### Offline regression tests

From the repository root, run:

```powershell
.\cowork-plugin\test_package.ps1
```

[test_package.ps1](test_package.ps1) parses the PowerShell files, verifies the exact mandatory parameter names, builds locally using a throwaway GUID and `example.com` URLs, reads archive JSON and skill references, checks source-template preservation, JSON escaping, branding, and icon dimensions/transparency. It exercises URL, GUID, publisher, placeholder, auth, and skill-reference rejection paths. Isolated test copies live under the ignored output folder and are removed afterward. **No endpoint calls, credentials, tunnel, registration, installation, or deployment.** Test fixtures are changed in memory and exercised through extracted script blocks, not by editing source files.

These tests do not prove full manifest schema acceptance, tenant installability, endpoint connectivity, MCP safety annotations, transport behavior, model grounding, or real authentication/authorization. Validate those separately before an approved remote demo.

## Install and demonstrate

Participants need a Microsoft 365 work account with Cowork access and tenant permission for custom apps. Follow the current [Microsoft Learn Cowork plugin guide](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) with your administrator: use its Agents Toolkit sign-in/personal sideloading flow for approved personal tests, or administrator review, upload, and group access for a shared demo. Find **Custom chat app** in Cowork's **Sources & Skills > Plugins** where available. Interface labels and availability can change; do not bypass policy. A personal install does not share the plugin with colleagues.

This ZIP **does not create a Copilot Chat declarative agent**. That separate integration is described in the [repository guide](../README.md#optional-microsoft-365-integrations); its templates are not packaged here.

Try a new Cowork task with this plugin enabled:

> Using the custom chat app's mock knowledge, summarize the fictional onboarding guidance. Cite only returned sources, label it demonstration data, and identify evidence gaps. If tools are unavailable, say so.

Other tasks: a table of fictional planning documents, a one-page service operations brief, or a 150–250 word onboarding email **draft only**. Acceptance requires actual successful MCP evidence calls in available activity details or sanitized diagnostics, citations matching returned findings, explicit fictional-data labeling, and honest no-result/error handling. Domain discovery alone or “Source: custom chat app” text is not proof. Do not expose secrets, inputs, or raw confidential traces in diagnostics.

## Production is a separate design

**Do not swap in a real endpoint and retain anonymous access.** A real service requires supported platform-registered authentication, server-side user/document authorization, tenant/data-handling review, allowed and denied request tests, and an updated packaging contract. Keep secrets in the approved platform credential store, never manifests, skills, ZIPs, or traces. Cowork connector authorization and Copilot Chat plugin authentication are different configuration surfaces; do not copy one blindly. This mock package implements neither delegated identity nor enterprise permission enforcement. See [../SECURITY.md](../SECURITY.md).

## Troubleshooting

| Problem | Check |
| --- | --- |
| Packaging rejects input | Supply all six actual values; check the local validation contract, without sharing secrets |
| Skill rejected/not loaded | Exact renamed folder, single matching frontmatter, archive reference |
| Upload rejected | Current platform schema validation, root layout, icons, legal metadata, tenant policy |
| Plugin missing | Same work account, Cowork availability, tenant installation and assigned access |
| MCP unavailable | Exact packaged URL, server/tunnel uptime, complete MCP path, host/origin allowlists |
| Tunnel 502 | Forward to local HTTP on the MCP port |
| No mock evidence | Inspect calls; report failure, not fluent uncited success |
| No file/email artifact | Expected: these skills return text only and perform no writes or sends |

## References and rights

Microsoft Learn guidance checked on October 2, 2026:

- [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development): v1.28 manifest, connector, skill, ZIP, icon, and installation rules.
- [Configure MCP and API plugin authentication](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/plugin-authentication): authentication and the distinct connector configuration surface.

No source license, ownership, or publisher affiliation is assigned by this plugin. Choose a license and verify source, contributor, branding, and redistribution rights before distribution.
