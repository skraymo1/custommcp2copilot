#requires -Version 5.1
<# Offline Windows tests. No Pester dependency, endpoint calls, or deployment. #>
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:passed = 0

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw "FAIL: $Message" }
}
function Test-Case([string]$Name, [scriptblock]$Body) {
    & $Body
    $script:passed++
    Write-Host "PASS: $Name"
}
function Assert-Rejected([scriptblock]$Body, [string]$Expected) {
    $caught = $null
    try { & $Body | Out-Null } catch { $caught = $_ }
    Assert-True ($null -ne $caught) 'Expected rejection'
    Assert-True ($caught.Exception.Message -match $Expected) 'Expected validation error category'
    Assert-True ($caught.Exception.Message -notmatch 'ACCIDENTAL_SECRET') 'Error must not echo input secrets'
}
function Read-ZipText($Archive, [string]$Name) {
    $entry = $Archive.GetEntry($Name)
    Assert-True ($null -ne $entry) "Archive entry $Name exists"
    $reader = New-Object IO.StreamReader ($entry.Open())
    try { return $reader.ReadToEnd() } finally { $reader.Dispose() }
}

$source = $PSScriptRoot
$testRoot = Join-Path $source ('dist/test-' + [Guid]::NewGuid().ToString('N'))
$packagePath = Join-Path $testRoot 'package.ps1'
$parameters = @{
    McpUrl = 'https://example.com/mcp'
    AppId = [Guid]::NewGuid().ToString('D')
    PublisherName = 'Offline demo publisher'
    WebsiteUrl = 'https://example.com'
    PrivacyUrl = 'https://example.com/privacy'
    TermsOfUseUrl = 'https://example.com/terms'
}

try {
    Test-Case 'PowerShell parser: packager and tests' {
        foreach ($file in @('package.ps1', 'test_package.ps1')) {
            $tokens = $errors = $null
            $ast = [Management.Automation.Language.Parser]::ParseFile((Join-Path $source $file), [ref]$tokens, [ref]$errors)
            Assert-True ($errors.Count -eq 0) "$file parses"
            if ($file -eq 'package.ps1') {
                $names = @($ast.ParamBlock.Parameters | ForEach-Object { $_.Name.VariablePath.UserPath })
                Assert-True ($names.Count -eq 6) 'Exactly six application parameters'
                foreach ($name in $parameters.Keys) { Assert-True ($names -contains $name) "Parameter $name exists" }
                $metadata = Get-Command (Join-Path $source $file)
                foreach ($name in $names) {
                    $attributes = @($metadata.Parameters[$name].Attributes | Where-Object { $_ -is [Management.Automation.ParameterAttribute] })
                    Assert-True ($attributes.Count -eq 1 -and $attributes[0].Mandatory) "$name is mandatory"
                }
            }
        }
    }

    New-Item -ItemType Directory -Path $testRoot -Force | Out-Null
    foreach ($name in @('manifest.json', 'package.ps1', 'skills')) {
        Copy-Item -LiteralPath (Join-Path $source $name) -Destination $testRoot -Recurse
    }
    $template = Get-Content -LiteralPath (Join-Path $source 'manifest.json') -Raw -Encoding UTF8
    $templateHash = (Get-FileHash -LiteralPath (Join-Path $source 'manifest.json')).Hash
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    Add-Type -AssemblyName System.Drawing

    Test-Case 'Local package and ZIP manifest/skills/branding/icons' {
        & $packagePath @parameters
        $archive = [IO.Compression.ZipFile]::OpenRead((Join-Path $testRoot 'dist/custom-chat-app.zip'))
        try {
            $files = @($archive.Entries | Where-Object { -not $_.FullName.EndsWith('/') })
            Assert-True ($files.Count -eq 5) 'Only manifest, two icons, two skills'
            $json = Read-ZipText $archive 'manifest.json'
            $manifest = $json | ConvertFrom-Json
            Assert-True ($manifest.id -eq $parameters.AppId) 'Supplied throwaway GUID'
            Assert-True ($manifest.name.short -ceq 'Custom chat app') 'Generic app name'
            Assert-True ($manifest.developer.name -ceq $parameters.PublisherName) 'Publisher'
            Assert-True ($manifest.developer.websiteUrl -ceq $parameters.WebsiteUrl) 'Website'
            Assert-True ($manifest.developer.privacyUrl -ceq $parameters.PrivacyUrl) 'Privacy'
            Assert-True ($manifest.developer.termsOfUseUrl -ceq $parameters.TermsOfUseUrl) 'Terms'
            Assert-True ($manifest.agentConnectors[0].id -ceq 'custom-chat-app-knowledge') 'Generic connector namespace'
            $remote = $manifest.agentConnectors[0].toolSource.remoteMcpServer
            Assert-True ($remote.mcpServerUrl -ceq $parameters.McpUrl) 'Endpoint preserved exactly'
            Assert-True ($remote.authorization.type -ceq 'None') 'Fictional mock anonymous auth'
            Assert-True ($remote.authorization.PSObject.Properties.Name -notcontains 'referenceId') 'No auth reference'
            $allText = $json
            foreach ($skill in $manifest.agentSkills) {
                $relative = $skill.folder.Substring(2) + '/SKILL.md'
                $text = Read-ZipText $archive $relative
                $allText += $text
                $name = $skill.folder.Split('/')[-1]
                Assert-True ($text -cmatch "(?m)^name: $name\r?$") 'Skill name matches archive folder'
                Assert-True ([regex]::Matches($text, '(?m)^---\r?$').Count -eq 2) 'Single frontmatter'
                foreach ($tool in @('list_knowledge_domains', 'search_knowledge', 'get_document', 'ask_knowledge')) {
                    Assert-True ($text.Contains($tool)) "Skill includes $tool"
                }
                Assert-True ($text.Contains('mock-knowledge') -and $text.Contains('demonstration_data=true')) 'Provenance contract'
            }
            Assert-True ($allText -notmatch '(?i)tellus|\bfao\b|48f36ba4|OneDrive|\{\{|\}\}') 'No legacy identity or unresolved placeholders'
            foreach ($spec in @(@('color.png', 192), @('outline.png', 32))) {
                $stream = $archive.GetEntry($spec[0]).Open()
                $image = [System.Drawing.Bitmap]::FromStream($stream)
                try {
                    Assert-True ($image.Width -eq $spec[1] -and $image.Height -eq $spec[1]) 'Correct icon dimensions'
                    Assert-True ($image.RawFormat.Guid -eq [Drawing.Imaging.ImageFormat]::Png.Guid) 'PNG icon'
                    if ($spec[0] -eq 'outline.png') {
                        Assert-True ($image.GetPixel(0, 0).A -eq 0) 'Transparent outline background'
                        $visible = 0
                        for ($x = 0; $x -lt $image.Width; $x++) {
                            for ($y = 0; $y -lt $image.Height; $y++) {
                                $pixel = $image.GetPixel($x, $y)
                                if ($pixel.A -gt 0) {
                                    $visible++
                                    Assert-True ($pixel.R -eq 255 -and $pixel.G -eq 255 -and $pixel.B -eq 255) 'White-only outline'
                                }
                            }
                        }
                        Assert-True ($visible -gt 0) 'Outline glyph present'
                    }
                } finally { $image.Dispose(); $stream.Dispose() }
            }
            $scriptText = Get-Content -LiteralPath $packagePath -Raw
            Assert-True ($scriptText.Contains("DrawString('C',")) 'Generic C glyph'
            Assert-True ($scriptText -notmatch '\s-replace\s') 'No regex JSON substitution'
        } finally { $archive.Dispose() }
        Assert-True ((Get-Content -LiteralPath (Join-Path $testRoot 'manifest.json') -Raw) -ceq $template) 'Copied source template unchanged'
        Assert-True ((Get-FileHash -LiteralPath (Join-Path $source 'manifest.json')).Hash -eq $templateHash) 'Real source template unchanged'
    }

    Test-Case 'Structured JSON handles quotes, backslashes, dollar signs and Unicode' {
        $escaped = $parameters.Clone()
        $escaped.PublisherName = 'Demo "C" \ $ café'
        $escaped.McpUrl = 'https://example.com:8443/demo/$mcp'
        & $packagePath @escaped
        $actual = Get-Content -LiteralPath (Join-Path $testRoot 'dist/build/manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        Assert-True ($actual.developer.name -ceq $escaped.PublisherName) 'Publisher round trip'
        Assert-True ($actual.agentConnectors[0].toolSource.remoteMcpServer.mcpServerUrl -ceq $escaped.McpUrl) 'URL round trip'
    }

    $zipHash = (Get-FileHash -LiteralPath (Join-Path $testRoot 'dist/custom-chat-app.zip')).Hash
    $badUrls = @(
        '', ' ', '/mcp', 'example.com/mcp', 'http://example.com/mcp', 'ftp://example.com/mcp',
        'https:///mcp', 'https://', 'https://user:ACCIDENTAL_SECRET@example.com/mcp',
        'https://@example.com/mcp', 'https://example.com/mcp?token=ACCIDENTAL_SECRET',
        'https://example.com/mcp?', 'https://example.com/mcp#ACCIDENTAL_SECRET', 'https://example.com/mcp#',
        'https://example.com:0/mcp', 'https://example.com:65536/mcp', 'https://example.com:abc/mcp',
        'https://*.example.com/mcp', 'https://%65xample.com/mcp', 'https://example.com\mcp',
        "https://example.com/`nACCIDENTAL_SECRET", ' https://example.com/mcp',
        'https://example.com/{{McpUrl}}', 'https://YOUR-HOST.example.com/mcp',
        'https://example.com/%7B%7BMcpUrl%7D%7D'
    )
    foreach ($key in @('McpUrl', 'WebsiteUrl', 'PrivacyUrl', 'TermsOfUseUrl')) {
        Test-Case "$key rejects $($badUrls.Count) unsafe URL variants" {
            foreach ($value in $badUrls) {
                $bad = $parameters.Clone(); $bad[$key] = $value
                Assert-Rejected { & $packagePath @bad } 'HTTPS|credentials|encoded host|placeholder|empty|argument'
            }
        }
    }
    Test-Case 'Invalid/empty/all-zero/noncanonical GUIDs' {
        foreach ($value in @('', ' ', 'not-a-guid', '00000000-0000-0000-0000-000000000000',
            $parameters.AppId.Replace('-', ''), ('{' + $parameters.AppId + '}'), '{{AppId}}')) {
            $bad = $parameters.Clone(); $bad.AppId = $value
            Assert-Rejected { & $packagePath @bad } 'GUID|placeholder|empty|argument'
        }
    }
    Test-Case 'Publisher constraints and unresolved placeholder formats' {
        foreach ($value in @('', ' ', ' demo', 'demo ', ('x' * 33), "demo`nACCIDENTAL_SECRET",
            '{{PublisherName}}', '${PublisherName}', '${{PublisherName}}', '$[PublisherName]',
            '<PublisherName>', '__PublisherName__', 'YOUR_NAME', 'REPLACE_ME', 'placeholder', '%7B%7Bx%7D%7D')) {
            $bad = $parameters.Clone(); $bad.PublisherName = $value
            Assert-Rejected { & $packagePath @bad } 'PublisherName|placeholder|empty|argument'
        }
    }
    Test-Case 'Rejected preflight preserves prior archive' {
        Assert-True ((Get-FileHash -LiteralPath (Join-Path $testRoot 'dist/custom-chat-app.zip')).Hash -eq $zipHash) 'No rejected input changes output'
    }

    # Exercise source-corruption gates in memory without editing even test source files.
    # The exact real preflight is extracted; only its root variable is redirected.
    $scriptText = Get-Content -LiteralPath $packagePath -Raw
    $prefix = $scriptText.Substring(0, $scriptText.IndexOf('# Validation finishes'))
    $preflight = [scriptblock]::Create($prefix.Replace('$root = $PSScriptRoot', '$root = $testRoot'))
    $script:fixtureManifest = $null
    $script:fixtureSkill = $null
    $script:missingSkill = $false
    function Get-Content {
        param([string]$LiteralPath, [switch]$Raw, [string]$Encoding)
        if ($LiteralPath.EndsWith('manifest.json') -and $null -ne $script:fixtureManifest) {
            return ($script:fixtureManifest | ConvertTo-Json -Depth 30)
        }
        if ($LiteralPath.EndsWith('SKILL.md') -and $null -ne $script:fixtureSkill) { return $script:fixtureSkill }
        Microsoft.PowerShell.Management\Get-Content -LiteralPath $LiteralPath -Raw -Encoding UTF8
    }
    function Test-Path {
        param([string]$LiteralPath, [string]$PathType)
        if ($script:missingSkill -and $LiteralPath.EndsWith('SKILL.md')) { return $false }
        Microsoft.PowerShell.Management\Test-Path -LiteralPath $LiteralPath -PathType $PathType
    }
    $mutations = @(
        @{ Name = 'Unresolved non-slot manifest field'; Error = 'placeholder'; Change = { param($m) $m.name.full = '{{Unresolved}}' } },
        @{ Name = 'Configured endpoint instead of source slot'; Error = 'template slots'; Change = { param($m) $m.agentConnectors[0].toolSource.remoteMcpServer.mcpServerUrl = 'https://example.com/mcp' } },
        @{ Name = 'Duplicate skill folders'; Error = 'distinct'; Change = { param($m) $m.agentSkills[1].folder = $m.agentSkills[0].folder } },
        @{ Name = 'Wrong skill count'; Error = 'distinct'; Change = { param($m) $m.agentSkills = @($m.agentSkills[0]) } },
        @{ Name = 'Unexpected/traversing skill path'; Error = 'Unexpected'; Change = { param($m) $m.agentSkills[0].folder = '../other-folder' } },
        @{ Name = 'Unexpected connector'; Error = 'connector'; Change = { param($m) $m.agentConnectors[0].id = 'other-connector' } },
        @{ Name = 'Nonmock auth'; Error = 'anonymous mock'; Change = { param($m) $m.agentConnectors[0].toolSource.remoteMcpServer.authorization.type = 'OAuthPluginVault' } },
        @{ Name = 'Anonymous auth reference'; Error = 'anonymous mock'; Change = { param($m) $m.agentConnectors[0].toolSource.remoteMcpServer.authorization | Add-Member referenceId 'unused' } },
        @{ Name = 'Unexpected icon path'; Error = 'icons'; Change = { param($m) $m.icons.color = '../other.png' } }
    )
    foreach ($mutation in $mutations) {
        Test-Case $mutation.Name {
            $script:fixtureManifest = $template | ConvertFrom-Json
            & $mutation.Change $script:fixtureManifest
            Assert-Rejected { & $preflight @parameters } $mutation.Error
            $script:fixtureManifest = $null
        }
    }
    Test-Case 'Missing instruction file' {
        $script:missingSkill = $true
        Assert-Rejected { & $preflight @parameters } 'missing'
        $script:missingSkill = $false
    }
    Test-Case 'Skill frontmatter mismatch, duplicate tail, empty description, placeholder' {
        foreach ($text in @(
            "---`nname: wrong-name`ndescription: |`n  Fictional demo`n---`nBody`n",
            "---`nname: knowledge-research`ndescription: |`n  Fictional demo`n---`nBody`n---`nlegacy`n---`n",
            "---`nname: knowledge-research`ndescription: |`n---`nBody`n",
            "---`nname: knowledge-research`ndescription: |`n  Fictional demo`n---`n{{Unresolved}}`n"
        )) {
            $script:fixtureSkill = $text
            Assert-Rejected { & $preflight @parameters } 'frontmatter|placeholder'
        }
        $script:fixtureSkill = $null
    }
    Write-Host "PASS: $script:passed test groups; offline only, no endpoint contacted or deployed."
}
finally {
    if (Microsoft.PowerShell.Management\Test-Path -LiteralPath $testRoot) {
        Remove-Item -LiteralPath $testRoot -Recurse -Force
    }
}