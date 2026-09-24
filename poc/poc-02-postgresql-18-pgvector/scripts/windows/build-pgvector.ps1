param(
    [string]$SourceRoot = "",
    [string]$PostgreSqlRoot = "D:\POC-02\postgresql-18.6\pgsql",
    [string]$BuildToolsRoot = "D:\POC-02\BuildTools",
    [string]$EvidenceRoot = ""
)

$ErrorActionPreference = "Stop"
$pocRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$repoRoot = (Resolve-Path (Join-Path $pocRoot "..\..")).Path
if (-not $SourceRoot) {
    $SourceRoot = Join-Path $repoRoot "artifacts\poc-02\windows\source\pgvector-0.8.6"
}
if (-not $EvidenceRoot) {
    $EvidenceRoot = Join-Path $repoRoot "artifacts\poc-02\windows-11\pgvector-build"
}

$resolvedSource = (Resolve-Path -LiteralPath $SourceRoot).Path
$resolvedPostgreSql = (Resolve-Path -LiteralPath $PostgreSqlRoot).Path
$vsDevCmd = Join-Path $BuildToolsRoot "Common7\Tools\VsDevCmd.bat"
$makefile = Join-Path $resolvedSource "Makefile.win"
$pgConfig = Join-Path $resolvedPostgreSql "bin\pg_config.exe"
$logPath = Join-Path $EvidenceRoot "build.log"
$resultPath = Join-Path $EvidenceRoot "result.json"

foreach ($requiredFile in @($vsDevCmd, $makefile, $pgConfig)) {
    if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
        throw "Required build input not found: $requiredFile"
    }
}

$sourceCommit = (& git -C $resolvedSource rev-parse HEAD | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $sourceCommit -ne "8ee86c96f0fd72390f890aa8a336fda6d3ab4c6c") {
    throw "Unexpected pgvector source commit: $sourceCommit"
}
$postgresqlVersion = (& $pgConfig --version | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $postgresqlVersion -ne "PostgreSQL 18.6") {
    throw "Unexpected PostgreSQL build target: $postgresqlVersion"
}

New-Item -ItemType Directory -Force -Path $EvidenceRoot | Out-Null
$command = @(
    "call `"$vsDevCmd`" -arch=amd64 -host_arch=amd64",
    "set `"PGROOT=$resolvedPostgreSql`"",
    "cd /d `"$resolvedSource`"",
    "nmake /F Makefile.win clean",
    "nmake /F Makefile.win",
    "nmake /F Makefile.win install"
) -join " && "

try {
    & $env:ComSpec /d /s /c $command 2>&1 | Tee-Object -FilePath $logPath
    if ($LASTEXITCODE -ne 0) {
        throw "pgvector build failed with exit code $LASTEXITCODE"
    }

    $installedDll = Join-Path $resolvedPostgreSql "lib\vector.dll"
    $installedControl = Join-Path $resolvedPostgreSql "share\extension\vector.control"
    $installedSql = Join-Path $resolvedPostgreSql "share\extension\vector--0.8.6.sql"
    foreach ($installedFile in @($installedDll, $installedControl, $installedSql)) {
        if (-not (Test-Path -LiteralPath $installedFile -PathType Leaf)) {
            throw "Expected pgvector file was not installed: $installedFile"
        }
    }

    [ordered]@{
        status = "PASS"
        pgvector_version = "0.8.6"
        source_commit = $sourceCommit
        postgresql_version = "18.6"
        architecture = "x64"
        vector_dll_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $installedDll).Hash.ToLowerInvariant()
        completed_at_utc = [DateTime]::UtcNow.ToString("o")
    } | ConvertTo-Json | Set-Content -LiteralPath $resultPath -Encoding UTF8
} catch {
    [ordered]@{
        status = "FAIL"
        error = $_.Exception.Message
        completed_at_utc = [DateTime]::UtcNow.ToString("o")
    } | ConvertTo-Json | Set-Content -LiteralPath $resultPath -Encoding UTF8
    throw
}
