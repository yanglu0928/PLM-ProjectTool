param(
    [string]$PostgreSqlRoot = "D:\POC-02\postgresql-18.6\pgsql",
    [string]$ArtifactRoot = ""
)

$ErrorActionPreference = "Stop"
$pocRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$repoRoot = (Resolve-Path (Join-Path $pocRoot "..\..")).Path
if (-not $ArtifactRoot) {
    $ArtifactRoot = Join-Path $repoRoot "artifacts\poc-02\windows-server-2025\bundle"
}

$resolvedPostgreSql = (Resolve-Path -LiteralPath $PostgreSqlRoot).Path
$pgConfig = Join-Path $resolvedPostgreSql "bin\pg_config.exe"
$vectorDll = Join-Path $resolvedPostgreSql "lib\vector.dll"
$vectorControl = Join-Path $resolvedPostgreSql "share\extension\vector.control"
$vectorSql = Join-Path $resolvedPostgreSql "share\extension\vector--0.8.6.sql"
foreach ($requiredFile in @($pgConfig, $vectorDll, $vectorControl, $vectorSql)) {
    if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
        throw "Required bundle input not found: $requiredFile"
    }
}
if ((& $pgConfig --version | Out-String).Trim() -ne "PostgreSQL 18.6") {
    throw "Unexpected PostgreSQL runtime version"
}

New-Item -ItemType Directory -Force -Path $ArtifactRoot | Out-Null
$stagingRoot = Join-Path $ArtifactRoot "staging-$PID"
$payloadRoot = Join-Path $stagingRoot "payload"
$runtimeStage = Join-Path $stagingRoot "runtime\pgsql"
$innerArchive = Join-Path $payloadRoot "postgresql-18.6-pgvector-0.8.6.zip"
$outerArchive = Join-Path $ArtifactRoot "poc-02-windows-server-2025-bundle.zip"
$manifestPath = Join-Path $payloadRoot "manifest.json"

if (Test-Path -LiteralPath $stagingRoot) {
    throw "Unique staging directory already exists: $stagingRoot"
}
New-Item -ItemType Directory -Force -Path $payloadRoot, $runtimeStage | Out-Null

try {
    foreach ($directory in @("bin", "lib", "share")) {
        Copy-Item -LiteralPath (Join-Path $resolvedPostgreSql $directory) -Destination $runtimeStage -Recurse
    }
    Copy-Item -LiteralPath (Join-Path $resolvedPostgreSql "server_license.txt") -Destination $runtimeStage
    Compress-Archive -LiteralPath $runtimeStage -DestinationPath $innerArchive -CompressionLevel Optimal

    Copy-Item -LiteralPath $pocRoot -Destination (Join-Path $payloadRoot "poc") -Recurse
    $manifest = [ordered]@{
        generated_at_utc = [DateTime]::UtcNow.ToString("o")
        target = "Windows Server 2025 x86-64"
        postgresql_version = "18.6"
        pgvector_version = "0.8.6"
        pgvector_source_commit = "8ee86c96f0fd72390f890aa8a336fda6d3ab4c6c"
        runtime_archive = [ordered]@{
            name = [IO.Path]::GetFileName($innerArchive)
            size_bytes = (Get-Item -LiteralPath $innerArchive).Length
            sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $innerArchive).Hash.ToLowerInvariant()
        }
        vector_dll_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $vectorDll).Hash.ToLowerInvariant()
    }
    $manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

    if (Test-Path -LiteralPath $outerArchive) {
        Remove-Item -LiteralPath $outerArchive -Force
    }
    Compress-Archive -Path (Join-Path $payloadRoot "*") -DestinationPath $outerArchive -CompressionLevel Optimal
    [ordered]@{
        status = "PASS"
        bundle = $outerArchive
        size_bytes = (Get-Item -LiteralPath $outerArchive).Length
        sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $outerArchive).Hash.ToLowerInvariant()
        runtime_archive_sha256 = $manifest.runtime_archive.sha256
    } | ConvertTo-Json
} finally {
    $resolvedArtifactRoot = (Resolve-Path -LiteralPath $ArtifactRoot).Path.TrimEnd('\') + '\'
    $resolvedStagingRoot = (Resolve-Path -LiteralPath $stagingRoot -ErrorAction SilentlyContinue).Path
    if ($resolvedStagingRoot -and $resolvedStagingRoot.StartsWith($resolvedArtifactRoot, [StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $resolvedStagingRoot -Recurse -Force
    }
}
