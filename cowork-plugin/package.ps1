#requires -Version 5.1
<#
.SYNOPSIS
  Package the custom chat app's fictional, read-only Cowork demo on Windows.
.DESCRIPTION
  All six parameters are required. No endpoint is contacted or deployed.
  See README.md for the validation contract and mock-only security boundary.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$McpUrl,
    [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$AppId,
    [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$PublisherName,
    [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$WebsiteUrl,
    [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$PrivacyUrl,
    [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$TermsOfUseUrl
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-Resolved([string]$Text, [string]$Label) {
    # Detection only: substitutions below assign JSON properties, never replace text.
    $decoded = [Uri]::UnescapeDataString($Text)
    if ($decoded -match '(?i)\{\{|\}\}|\$\{|\$\[|<[^>]*>|__[^\s]*__|YOUR[-_ ]|REPLACE[-_ ]?ME|PLACEHOLDER') {
        throw "$Label contains an unresolved placeholder."
    }
}

function Assert-HttpsUrl([string]$Value, [string]$Label) {
    Assert-Resolved $Value $Label
    $uri = $null
    if ($Value -match '[\s\x00-\x1f\x7f\\?#]' -or
        -not $Value.StartsWith('https://', [StringComparison]::OrdinalIgnoreCase) -or
        -not [Uri]::TryCreate($Value, [UriKind]::Absolute, [ref]$uri) -or
        $uri.Scheme -ne 'https' -or [string]::IsNullOrEmpty($uri.Host) -or
        $uri.HostNameType -eq [UriHostNameType]::Unknown -or
        $uri.Host.Contains('*') -or $uri.Host.Contains('%') -or
        -not [string]::IsNullOrEmpty($uri.UserInfo) -or
        -not [string]::IsNullOrEmpty($uri.Query) -or
        -not [string]::IsNullOrEmpty($uri.Fragment) -or $uri.Port -lt 1) {
        # Do not echo supplied URLs: they may accidentally contain credentials.
        throw "$Label must be an absolute HTTPS URL with an exact host, valid port, and no credentials, whitespace, backslashes, query, or fragment."
    }
    $authority = $Value.Substring(8).Split('/')[0]
    if ($authority.Contains('@') -or $authority.Contains('%')) {
        throw "$Label must not contain credentials or an encoded host."
    }
}

foreach ($entry in @{
    McpUrl = $McpUrl; WebsiteUrl = $WebsiteUrl
    PrivacyUrl = $PrivacyUrl; TermsOfUseUrl = $TermsOfUseUrl
}.GetEnumerator()) {
    Assert-HttpsUrl $entry.Value $entry.Key
}
Assert-Resolved $AppId 'AppId'
$guid = [Guid]::Empty
if (-not [Guid]::TryParseExact($AppId, 'D', [ref]$guid) -or $guid -eq [Guid]::Empty) {
    throw 'AppId must be a nonzero GUID in hyphenated D format.'
}
Assert-Resolved $PublisherName 'PublisherName'
if ([string]::IsNullOrWhiteSpace($PublisherName) -or $PublisherName.Length -gt 32 -or
    $PublisherName -ne $PublisherName.Trim() -or $PublisherName -match '[\x00-\x1f\x7f]') {
    throw 'PublisherName must be 1-32 characters, without surrounding whitespace or control characters.'
}

$root = $PSScriptRoot
$manifest = Get-Content -LiteralPath (Join-Path $root 'manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if (@($manifest.agentConnectors).Count -ne 1 -or
    $manifest.agentConnectors[0].id -cne 'custom-chat-app-knowledge') {
    throw 'Expected exactly one custom-chat-app-knowledge connector.'
}
$remote = $manifest.agentConnectors[0].toolSource.remoteMcpServer
if ($remote.authorization.type -cne 'None' -or
    $remote.authorization.PSObject.Properties.Name -contains 'referenceId') {
    throw 'This packager supports only the fictional anonymous mock (None, no referenceId).'
}

# Require the six source template slots; never silently overwrite a configured service.
$slots = @(
    @($manifest.id, '{{AppId}}'),
    @($manifest.developer.name, '{{PublisherName}}'),
    @($manifest.developer.websiteUrl, '{{WebsiteUrl}}'),
    @($manifest.developer.privacyUrl, '{{PrivacyUrl}}'),
    @($manifest.developer.termsOfUseUrl, '{{TermsOfUseUrl}}'),
    @($remote.mcpServerUrl, '{{McpUrl}}')
)
foreach ($slot in $slots) {
    if ($slot[0] -cne $slot[1]) { throw 'Manifest must retain the documented six source template slots.' }
}
$manifest.id = $guid.ToString('D')
$manifest.developer.name = $PublisherName
$manifest.developer.websiteUrl = $WebsiteUrl
$manifest.developer.privacyUrl = $PrivacyUrl
$manifest.developer.termsOfUseUrl = $TermsOfUseUrl
$remote.mcpServerUrl = $McpUrl
$json = $manifest | ConvertTo-Json -Depth 30
Assert-Resolved $json 'Generated manifest'

$expectedFolders = @('./skills/knowledge-research', './skills/knowledge-briefing')
$folders = @($manifest.agentSkills | ForEach-Object { $_.folder })
if ($folders.Count -ne 2 -or @($folders | Select-Object -Unique).Count -ne 2) {
    throw 'Manifest must reference exactly the two distinct knowledge skill folders.'
}
foreach ($folder in $folders) {
    if ($expectedFolders -cnotcontains $folder) { throw 'Unexpected skill folder reference.' }
    $path = Join-Path $root $folder
    $skillPath = Join-Path $path 'SKILL.md'
    if (-not (Test-Path -LiteralPath $path -PathType Container) -or
        -not (Test-Path -LiteralPath $skillPath -PathType Leaf)) {
        throw 'Referenced skill folder or SKILL.md is missing.'
    }
    if ((Get-Item -LiteralPath $path).Attributes -band [IO.FileAttributes]::ReparsePoint -or
        (Get-Item -LiteralPath $skillPath).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw 'Skill folders and files must not be links.'
    }
    $text = Get-Content -LiteralPath $skillPath -Raw -Encoding UTF8
    $name = Split-Path $path -Leaf
    $frontmatter = [regex]::Match($text, '\A---\r?\n(?<fields>.*?)\r?\n---\r?\n', 'Singleline')
    if (-not $frontmatter.Success -or [regex]::Matches($text, '(?m)^---\r?$').Count -ne 2 -or
        $frontmatter.Groups['fields'].Value -cnotmatch "(?m)^name: $name\r?$" -or
        $frontmatter.Groups['fields'].Value -notmatch '(?m)^description: (?:\|\r?\n  \S|[A-Za-z0-9][^\r\n]+)') {
        throw 'Skill must have a single frontmatter block, matching name, and nonblank plain or block description.'
    }
    Assert-Resolved $text 'Skill'
}
if ($manifest.icons.color -cne 'color.png' -or $manifest.icons.outline -cne 'outline.png') {
    throw 'Manifest must reference the generated color.png and outline.png icons.'
}

function New-Icon([string]$Path, [int]$Size, [bool]$Outline) {
    $bmp = $graphics = $font = $format = $null
    try {
        $bmp = New-Object System.Drawing.Bitmap $Size, $Size
        $graphics = [System.Drawing.Graphics]::FromImage($bmp)
        $graphics.SmoothingMode = 'AntiAlias'
        $graphics.TextRenderingHint = 'AntiAlias'
        if ($Outline) { $graphics.Clear([System.Drawing.Color]::Transparent) }
        else { $graphics.Clear([System.Drawing.ColorTranslator]::FromHtml('#0F6CBD')) }
        $font = New-Object System.Drawing.Font 'Segoe UI', ($Size * 0.55), ([System.Drawing.FontStyle]::Bold), ([System.Drawing.GraphicsUnit]::Pixel)
        $format = New-Object System.Drawing.StringFormat
        $format.Alignment = 'Center'
        $format.LineAlignment = 'Center'
        $rect = New-Object System.Drawing.RectangleF 0, 0, $Size, $Size
        $graphics.DrawString('C', $font, [System.Drawing.Brushes]::White, $rect, $format)
        if ($Outline) {
            # GDI+ antialiasing may leave gray RGB values on a transparent bitmap.
            # Keep the coverage alpha but make every visible pixel single-color white.
            for ($x = 0; $x -lt $Size; $x++) {
                for ($y = 0; $y -lt $Size; $y++) {
                    $alpha = $bmp.GetPixel($x, $y).A
                    if ($alpha -gt 0) {
                        $bmp.SetPixel($x, $y, [System.Drawing.Color]::FromArgb($alpha, 255, 255, 255))
                    }
                }
            }
        }
        $bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    }
    finally {
        foreach ($resource in @($format, $font, $graphics, $bmp)) {
            if ($null -ne $resource) { $resource.Dispose() }
        }
    }
}

# Validation finishes before touching generated output. Always generate generic C icons;
# source icons or unrelated skill directories cannot silently add old branding.
Add-Type -AssemblyName System.Drawing
$build = Join-Path $root 'dist/build'
if (Test-Path -LiteralPath $build) { Remove-Item -LiteralPath $build -Recurse -Force }
New-Item -ItemType Directory -Path $build -Force | Out-Null
$utf8 = New-Object System.Text.UTF8Encoding $false
[IO.File]::WriteAllText((Join-Path $build 'manifest.json'), $json, $utf8)
New-Icon (Join-Path $build 'color.png') 192 $false
New-Icon (Join-Path $build 'outline.png') 32 $true
foreach ($folder in $folders) {
    $destination = Join-Path $build $folder
    New-Item -ItemType Directory -Path $destination -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path (Join-Path $root $folder) 'SKILL.md') -Destination $destination
}
$zip = Join-Path $root 'dist/custom-chat-app.zip'
Compress-Archive -Path (Join-Path $build '*') -DestinationPath $zip -Force
Write-Host "Built $zip (fictional anonymous mock only; not deployed)."
