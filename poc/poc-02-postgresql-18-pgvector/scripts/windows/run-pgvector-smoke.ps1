param(
    [string]$RuntimeRoot = "D:\POC-02\postgresql-18.6",
    [int]$Port = 55432,
    [string]$EvidenceRoot = ""
)

$ErrorActionPreference = "Stop"
$pocRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$repoRoot = (Resolve-Path (Join-Path $pocRoot "..\..")).Path
if (-not $EvidenceRoot) {
    $EvidenceRoot = Join-Path $repoRoot "artifacts\poc-02\windows-11\pgvector-smoke"
}

$postgresqlRoot = Join-Path $RuntimeRoot "pgsql"
$dataRoot = Join-Path $RuntimeRoot "data"
$runtimeLogPath = Join-Path $RuntimeRoot "postgresql.log"
$runtimeSql = Join-Path $RuntimeRoot "pgvector-smoke.sql"
$sourceSql = Join-Path $pocRoot "sql\pgvector-smoke.sql"
$pgCtl = Join-Path $postgresqlRoot "bin\pg_ctl.exe"
$psql = Join-Path $postgresqlRoot "bin\psql.exe"
$vectorDll = Join-Path $postgresqlRoot "lib\vector.dll"
$logPath = Join-Path $EvidenceRoot "postgresql.log"
$sqlOutputPath = Join-Path $EvidenceRoot "smoke-sql.txt"
$resultPath = Join-Path $EvidenceRoot "result.json"

foreach ($requiredFile in @($pgCtl, $psql, $vectorDll, $sourceSql, (Join-Path $dataRoot "PG_VERSION"))) {
    if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
        throw "Required pgvector smoke-test input not found: $requiredFile"
    }
}
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
    throw "Port $Port is already in use"
}

New-Item -ItemType Directory -Force -Path $EvidenceRoot | Out-Null
Copy-Item -LiteralPath $sourceSql -Destination $runtimeSql -Force
$started = $false
try {
    & $pgCtl -D $dataRoot -l $runtimeLogPath -w start
    if ($LASTEXITCODE -ne 0) {
        throw "pg_ctl start failed with exit code $LASTEXITCODE"
    }
    $started = $true

    & $psql -X -v ON_ERROR_STOP=1 -h 127.0.0.1 -p $Port -U poc_admin -d postgres -f $runtimeSql 2>&1 |
        Tee-Object -FilePath $sqlOutputPath
    if ($LASTEXITCODE -ne 0) {
        throw "pgvector smoke SQL failed with exit code $LASTEXITCODE"
    }

    $extensionVersion = (& $psql -X -h 127.0.0.1 -p $Port -U poc_admin -d postgres -Atc "SELECT extversion FROM pg_extension WHERE extname='vector';" | Out-String).Trim()
    $rowCount = [int]((& $psql -X -h 127.0.0.1 -p $Port -U poc_admin -d postgres -Atc "SELECT count(*) FROM poc02_vectors;" | Out-String).Trim())
    $indexMethod = (& $psql -X -h 127.0.0.1 -p $Port -U poc_admin -d postgres -Atc "SELECT am.amname FROM pg_class c JOIN pg_am am ON am.oid=c.relam WHERE c.relname='poc02_vectors_hnsw_idx';" | Out-String).Trim()
    $nearestLabel = (& $psql -X -h 127.0.0.1 -p $Port -U poc_admin -d postgres -Atc "SELECT label FROM poc02_vectors ORDER BY embedding <-> '[0,0,0]'::vector LIMIT 1;" | Out-String).Trim()

    if ($extensionVersion -ne "0.8.6" -or $rowCount -ne 2 -or $indexMethod -ne "hnsw" -or $nearestLabel -ne "origin") {
        throw "Unexpected pgvector result: version=$extensionVersion rows=$rowCount index=$indexMethod nearest=$nearestLabel"
    }

    [ordered]@{
        status = "PASS"
        postgresql_version = "18.6"
        pgvector_version = $extensionVersion
        vector_dll_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $vectorDll).Hash.ToLowerInvariant()
        row_count_after_crud = $rowCount
        hnsw_index_method = $indexMethod
        nearest_label = $nearestLabel
        port = $Port
        listen_address = "127.0.0.1"
        authentication = "trust (isolated loopback PoC only)"
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
