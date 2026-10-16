param(
    [string]$ArtifactRoot = "",
    [string]$GitHubResolveAddress = ""
)

$ErrorActionPreference = "Stop"
$pocRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$repoRoot = (Resolve-Path (Join-Path $pocRoot "..\..")).Path
if (-not $ArtifactRoot) {
    $ArtifactRoot = Join-Path $repoRoot "artifacts\poc-02\windows"
}

$downloadRoot = Join-Path $ArtifactRoot "downloads"
$manifestPath = Join-Path $ArtifactRoot "asset-manifest.json"
New-Item -ItemType Directory -Force -Path $downloadRoot | Out-Null

$assets = @(
    [ordered]@{
        name = "postgresql-18.6-1-windows-x64.exe"
        url = "https://get.enterprisedb.com/postgresql/postgresql-18.6-1-windows-x64.exe"
        expected_size = 375833688
        source = "EDB installer linked from PostgreSQL.org"
    },
    [ordered]@{
        name = "postgresql-18.6-1-windows-x64-binaries.zip"
        url = "https://get.enterprisedb.com/postgresql/postgresql-18.6-1-windows-x64-binaries.zip"
        expected_size = 343808005
        source = "EDB binary archive linked from PostgreSQL.org"
    },
    [ordered]@{
        name = "pgvector-0.8.6.zip"
        url = "https://github.com/pgvector/pgvector/archive/refs/tags/v0.8.6.zip"
        expected_size = $null
        source = "pgvector official GitHub tag v0.8.6"
    },
    [ordered]@{
        name = "vs_BuildTools-17.14.41.exe"
        url = "https://download.visualstudio.microsoft.com/download/pr/bc92e2cb-33de-4a0c-995d-efa817f16b16/37bb0fb429d163ecebd272a865d11a37b906d152bef960da2ddb29c2e2fd6eeb/vs_BuildTools.exe"
        expected_size = 4473792
        expected_sha256 = "37bb0fb429d163ecebd272a865d11a37b906d152bef960da2ddb29c2e2fd6eeb"
        source = "Microsoft winget manifest for Visual Studio Build Tools 2022 17.14.41"
    }
)

$curl = Get-Command "curl.exe" -ErrorAction SilentlyContinue
if (-not $curl) {
    throw "curl.exe is required for resumable downloads"
}

$results = @()
foreach ($asset in $assets) {
    $destination = Join-Path $downloadRoot $asset.name
    if ($asset.name -eq "pgvector-0.8.6.zip") {
        $existingClone = Join-Path $ArtifactRoot "source\pgvector-0.8.6"
        if (Test-Path -LiteralPath (Join-Path $existingClone ".git") -PathType Container) {
            $existingCommit = (& git.exe -C $existingClone rev-parse HEAD | Out-String).Trim()
            if ($existingCommit -ne "8ee86c96f0fd72390f890aa8a336fda6d3ab4c6c") {
                throw "Unexpected pgvector source commit: $existingCommit"
            }
            if (-not (Test-Path -LiteralPath $destination -PathType Leaf) -or (Get-Item -LiteralPath $destination).Length -eq 0) {
                if (Test-Path -LiteralPath $destination) {
                    Remove-Item -LiteralPath $destination -Force
                }
                Compress-Archive -Path $existingClone -DestinationPath $destination -CompressionLevel Optimal
            }
        }
    }
    $needsDownload = -not (Test-Path -LiteralPath $destination -PathType Leaf)
    if (-not $needsDownload -and $asset.expected_size) {
        $needsDownload = (Get-Item -LiteralPath $destination).Length -ne $asset.expected_size
    }
    if (-not $needsDownload -and -not $asset.expected_size) {
        $needsDownload = (Get-Item -LiteralPath $destination).Length -eq 0
    }

    if ($needsDownload) {
        & $curl.Source `
            --fail `
            --location `
            --retry 3 `
            --retry-delay 2 `
            --connect-timeout 30 `
            --speed-limit 1024 `
            --speed-time 30 `
            --continue-at - `
            --output $destination `
            $asset.url
        if ($LASTEXITCODE -ne 0) {
            if ($asset.name -ne "pgvector-0.8.6.zip") {
                throw "Download failed: $($asset.name)"
            }

            $sourceRoot = Join-Path $ArtifactRoot "source"
            $clonePath = Join-Path $sourceRoot "pgvector-0.8.6"
            New-Item -ItemType Directory -Force -Path $sourceRoot | Out-Null
            if (-not (Test-Path -LiteralPath (Join-Path $clonePath ".git") -PathType Container)) {
                $gitArguments = @()
                if ($GitHubResolveAddress) {
                    $gitArguments += @("-c", "http.curloptResolve=+github.com:443:$GitHubResolveAddress")
                }
                $gitArguments += @("clone", "--branch", "v0.8.6", "--depth", "1", "https://github.com/pgvector/pgvector.git", $clonePath)
                & git.exe @gitArguments
                if ($LASTEXITCODE -ne 0) {
                    throw "pgvector tag archive and git clone both failed"
                }
            }
            $sourceCommit = (& git.exe -C $clonePath rev-parse HEAD | Out-String).Trim()
            if ($sourceCommit -ne "8ee86c96f0fd72390f890aa8a336fda6d3ab4c6c") {
                throw "Unexpected pgvector source commit: $sourceCommit"
            }
            if (Test-Path -LiteralPath $destination) {
                Remove-Item -LiteralPath $destination -Force
            }
            Compress-Archive -Path $clonePath -DestinationPath $destination -CompressionLevel Optimal
        }
    }

    $file = Get-Item -LiteralPath $destination
    if ($asset.expected_size -and $file.Length -ne $asset.expected_size) {
        throw "Unexpected size for $($asset.name): $($file.Length)"
    }
    $sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $destination).Hash.ToLowerInvariant()
    if ($asset.expected_sha256 -and $sha256 -ne $asset.expected_sha256) {
        throw "SHA-256 mismatch for $($asset.name)"
    }
    $results += [ordered]@{
        name = $asset.name
        url = $asset.url
        source = $asset.source
        size_bytes = $file.Length
        sha256 = $sha256
    }
}

$manifest = [ordered]@{
    generated_at_utc = [DateTime]::UtcNow.ToString("o")
    postgresql_version = "18.6"
    pgvector_version = "0.8.6"
    pgvector_tag_commit = "8ee86c96f0fd72390f890aa8a336fda6d3ab4c6c"
    assets = $results
}
$manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
$manifest | ConvertTo-Json -Depth 6
