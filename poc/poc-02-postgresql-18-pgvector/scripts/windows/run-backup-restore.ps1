param(
    [string]$RuntimeRoot = "D:\POC-02\postgresql-18.6",
    [int]$Port = 55432,
    [string]$EvidenceRoot = ""
)

$ErrorActionPreference = "Stop"
$pocRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$repoRoot = (Resolve-Path (Join-Path $pocRoot "..\..")).Path
if (-not $EvidenceRoot) {
    $EvidenceRoot = Join-Path $repoRoot "artifacts\poc-02\windows-11\backup-restore"
}

$postgresqlRoot = Join-Path $RuntimeRoot "pgsql"
$dataRoot = Join-Path $RuntimeRoot "data"
$pgCtl = Join-Path $postgresqlRoot "bin\pg_ctl.exe"
$psql = Join-Path $postgresqlRoot "bin\psql.exe"
$pgDump = Join-Path $postgresqlRoot "bin\pg_dump.exe"
$pgRestore = Join-Path $postgresqlRoot "bin\pg_restore.exe"
$runtimeLogPath = Join-Path $RuntimeRoot "postgresql.log"
$serverLogPath = Join-Path $EvidenceRoot "postgresql.log"
$dumpLogPath = Join-Path $EvidenceRoot "pg-dump.log"
$restoreLogPath = Join-Path $EvidenceRoot "pg-restore.log"
$dumpPath = Join-Path $EvidenceRoot "poc02-benchmark.dump"
$resultPath = Join-Path $EvidenceRoot "result.json"
$sourceDatabase = "poc02_benchmark"
$restoreDatabase = "poc02_restore"

foreach ($requiredFile in @($pgCtl, $psql, $pgDump, $pgRestore, (Join-Path $dataRoot "PG_VERSION"))) {
    if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
        throw "Required backup/restore input not found: $requiredFile"
    }
}
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
    throw "Port $Port is already in use"
}

function Invoke-ScalarQuery {
    param([string]$Database, [string]$Sql)
    $value = (& $psql -X -h 127.0.0.1 -p $Port -U poc_admin -d $Database -Atc $Sql | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) { throw "SQL scalar query failed for database $Database" }
    return $value
}

New-Item -ItemType Directory -Force -Path $EvidenceRoot | Out-Null
Set-Content -LiteralPath $dumpLogPath -Value "" -Encoding UTF8
Set-Content -LiteralPath $restoreLogPath -Value "" -Encoding UTF8
$started = $false
try {
    & $pgCtl -D $dataRoot -l $runtimeLogPath -w start
    if ($LASTEXITCODE -ne 0) { throw "pg_ctl start failed with exit code $LASTEXITCODE" }
    $started = $true

    $sourceCountBefore = [int64](Invoke-ScalarQuery -Database $sourceDatabase -Sql "SELECT count(*) FROM poc02_benchmark_vectors;")
    $sourceIdSumBefore = [int64](Invoke-ScalarQuery -Database $sourceDatabase -Sql "SELECT sum(id) FROM poc02_benchmark_vectors;")
    if ($sourceCountBefore -ne 100000 -or $sourceIdSumBefore -ne 5000050000) {
        throw "Source benchmark data is incomplete before backup"
    }

    & $pgDump -h 127.0.0.1 -p $Port -U poc_admin -d $sourceDatabase `
        --format=custom --compress=6 --no-owner --no-privileges --file=$dumpPath 2>&1 |
        Tee-Object -FilePath $dumpLogPath
    if ($LASTEXITCODE -ne 0) { throw "pg_dump failed with exit code $LASTEXITCODE" }

    & $psql -X -v ON_ERROR_STOP=1 -h 127.0.0.1 -p $Port -U poc_admin -d postgres `
        -c "DROP DATABASE IF EXISTS $restoreDatabase WITH (FORCE);" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Restore database cleanup failed" }
    & $psql -X -v ON_ERROR_STOP=1 -h 127.0.0.1 -p $Port -U poc_admin -d postgres `
        -c "CREATE DATABASE $restoreDatabase;" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Restore database creation failed" }

    & $pgRestore -h 127.0.0.1 -p $Port -U poc_admin -d $restoreDatabase `
        --exit-on-error --no-owner --no-privileges $dumpPath 2>&1 |
        Tee-Object -FilePath $restoreLogPath
    if ($LASTEXITCODE -ne 0) { throw "pg_restore failed with exit code $LASTEXITCODE" }

    $restoredCount = [int64](Invoke-ScalarQuery -Database $restoreDatabase -Sql "SELECT count(*) FROM poc02_benchmark_vectors;")
    $restoredIdSum = [int64](Invoke-ScalarQuery -Database $restoreDatabase -Sql "SELECT sum(id) FROM poc02_benchmark_vectors;")
    $restoredVectorVersion = Invoke-ScalarQuery -Database $restoreDatabase -Sql "SELECT extversion FROM pg_extension WHERE extname='vector';"
    $restoredIndexMethod = Invoke-ScalarQuery -Database $restoreDatabase -Sql "SELECT am.amname FROM pg_class c JOIN pg_am am ON am.oid=c.relam WHERE c.relname='poc02_benchmark_hnsw_idx';"
    if ($restoredCount -ne $sourceCountBefore -or $restoredIdSum -ne $sourceIdSumBefore -or $restoredVectorVersion -ne "0.8.6" -or $restoredIndexMethod -ne "hnsw") {
        throw "Restored data, extension, or HNSW index verification failed"
    }

    & $pgCtl -D $dataRoot -m fast -w stop | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Pre-health-check stop failed" }
    $started = $false
    # Do not pipe this start command: the spawned server can retain an inherited
    # output handle and keep a PowerShell pipeline open until the server stops.
    & $pgCtl -D $dataRoot -l $runtimeLogPath -w start
    if ($LASTEXITCODE -ne 0) { throw "Health-check restart failed" }
    $started = $true

    $sourceCountAfterRestart = [int64](Invoke-ScalarQuery -Database $sourceDatabase -Sql "SELECT count(*) FROM poc02_benchmark_vectors;")
    $restoredCountAfterRestart = [int64](Invoke-ScalarQuery -Database $restoreDatabase -Sql "SELECT count(*) FROM poc02_benchmark_vectors;")
    if ($sourceCountAfterRestart -ne 100000 -or $restoredCountAfterRestart -ne 100000) {
        throw "Restart health check failed"
    }

    [ordered]@{
        status = "PASS"
        postgresql_version = "18.6"
        pgvector_version = $restoredVectorVersion
        source_database = $sourceDatabase
        restored_database = $restoreDatabase
        source_row_count = $sourceCountBefore
        restored_row_count = $restoredCount
        source_id_sum = $sourceIdSumBefore
        restored_id_sum = $restoredIdSum
        restored_index_method = $restoredIndexMethod
        dump_size_bytes = (Get-Item -LiteralPath $dumpPath).Length
        dump_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $dumpPath).Hash.ToLowerInvariant()
        restart_health_check = "PASS"
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
    if ($started) { & $pgCtl -D $dataRoot -m fast -w stop | Out-Null }
    if (Test-Path -LiteralPath $runtimeLogPath -PathType Leaf) {
        Copy-Item -LiteralPath $runtimeLogPath -Destination $serverLogPath -Force
    }
}
