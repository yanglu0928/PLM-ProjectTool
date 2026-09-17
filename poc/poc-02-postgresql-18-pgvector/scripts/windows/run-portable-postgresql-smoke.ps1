param(
    [Parameter(Mandatory = $true)]
    [string]$PostgreSqlArchive,
    [string]$RuntimeRoot = "",
    [int]$Port = 55432,
    [string]$EvidenceRoot = ""
)

$ErrorActionPreference = "Stop"
$pocRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$repoRoot = (Resolve-Path (Join-Path $pocRoot "..\..")).Path
$resolvedArchive = (Resolve-Path -LiteralPath $PostgreSqlArchive).Path
if (-not $RuntimeRoot) {
    $runtimeDrive = if (Test-Path -LiteralPath "D:\") { "D:\" } else { "C:\" }
    $RuntimeRoot = Join-Path $runtimeDrive "POC-02\postgresql-18.6"
}
if (-not $EvidenceRoot) {
    $EvidenceRoot = Join-Path $repoRoot "artifacts\poc-02\windows-11\portable-smoke"
}

$extractRoot = Join-Path $RuntimeRoot "pgsql"
$dataRoot = Join-Path $RuntimeRoot "data"
$runtimeLogPath = Join-Path $RuntimeRoot "postgresql.log"
$logPath = Join-Path $EvidenceRoot "postgresql.log"
$sqlOutputPath = Join-Path $EvidenceRoot "smoke-sql.txt"
$resultPath = Join-Path $EvidenceRoot "result.json"
$sourceSmokeSql = Join-Path $pocRoot "sql\postgresql-smoke.sql"
$runtimeSmokeSql = Join-Path $RuntimeRoot "postgresql-smoke.sql"

New-Item -ItemType Directory -Force -Path $RuntimeRoot, $EvidenceRoot | Out-Null
Copy-Item -LiteralPath $sourceSmokeSql -Destination $runtimeSmokeSql -Force
if (-not (Test-Path -LiteralPath (Join-Path $extractRoot "bin\postgres.exe") -PathType Leaf)) {
    Expand-Archive -LiteralPath $resolvedArchive -DestinationPath $RuntimeRoot -Force
}

$initdb = Join-Path $extractRoot "bin\initdb.exe"
$pgCtl = Join-Path $extractRoot "bin\pg_ctl.exe"
$psql = Join-Path $extractRoot "bin\psql.exe"
$postgres = Join-Path $extractRoot "bin\postgres.exe"
foreach ($executable in @($initdb, $pgCtl, $psql, $postgres)) {
    if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
        throw "PostgreSQL executable not found: $([IO.Path]::GetFileName($executable))"
    }
}

if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
    throw "Port $Port is already in use"
}

$started = $false
try {
    if (-not (Test-Path -LiteralPath (Join-Path $dataRoot "PG_VERSION") -PathType Leaf)) {
        & $initdb `
            --pgdata=$dataRoot `
            --username=poc_admin `
            --auth=trust `
            --encoding=UTF8 `
            --locale=C
        if ($LASTEXITCODE -ne 0) {
            throw "initdb failed with exit code $LASTEXITCODE"
        }
        Add-Content -LiteralPath (Join-Path $dataRoot "postgresql.conf") -Encoding UTF8 -Value @(
            "listen_addresses = '127.0.0.1'",
            "port = $Port",
            "max_connections = 20"
        )
    }

    & $pgCtl -D $dataRoot -l $runtimeLogPath -w start
    if ($LASTEXITCODE -ne 0) {
        throw "pg_ctl start failed with exit code $LASTEXITCODE"
    }
    $started = $true

    $versionText = (& $psql -X -h 127.0.0.1 -p $Port -U poc_admin -d postgres -Atc "SELECT version();" | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $versionText -notmatch "PostgreSQL 18\.6") {
        throw "Unexpected PostgreSQL version output"
    }

    $savedErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $psql -X -v ON_ERROR_STOP=1 -h 127.0.0.1 -p $Port -U poc_admin -d postgres -f $runtimeSmokeSql 2>&1 |
            Tee-Object -FilePath $sqlOutputPath
        $psqlExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $savedErrorActionPreference
    }
    if ($psqlExitCode -ne 0) {
        throw "PostgreSQL smoke SQL failed with exit code $psqlExitCode"
    }

    $rowCount = [int]((& $psql -X -h 127.0.0.1 -p $Port -U poc_admin -d postgres -Atc "SELECT count(*) FROM poc02_smoke;" | Out-String).Trim())
    if ($rowCount -ne 3) {
        throw "Unexpected smoke row count: $rowCount"
    }

    [ordered]@{
        status = "PASS"
        postgresql_version = "18.6"
        archive_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $resolvedArchive).Hash.ToLowerInvariant()
        port = $Port
        listen_address = "127.0.0.1"
        authentication = "trust (isolated loopback PoC only)"
        row_count = $rowCount
        completed_at_utc = [DateTime]::UtcNow.ToString("o")
    } | ConvertTo-Json | Set-Content -LiteralPath $resultPath -Encoding UTF8
} catch {
    [ordered]@{
        status = "FAIL"
        error = $_.Exception.Message
        completed_at_utc = [DateTime]::UtcNow.ToString("o")
    } | ConvertTo-Json | Set-Content -LiteralPath $resultPath -Encoding UTF8
    throw
} finally {
    if ($started) {
        & $pgCtl -D $dataRoot -m fast -w stop | Out-Null
    }
    if (Test-Path -LiteralPath $runtimeLogPath -PathType Leaf) {
        Copy-Item -LiteralPath $runtimeLogPath -Destination $logPath -Force
    }
}
