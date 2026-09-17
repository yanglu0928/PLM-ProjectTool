param(
    [string]$PythonExecutable = "",
    [string]$RuntimeRoot = "D:\POC-02\postgresql-18.6",
    [int]$Port = 55432,
    [string]$EvidenceRoot = ""
)

$ErrorActionPreference = "Stop"
$pocRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$repoRoot = (Resolve-Path (Join-Path $pocRoot "..\..")).Path
if (-not $PythonExecutable) {
    $PythonExecutable = Join-Path $repoRoot ".poc-runtime\poc-01\windows-offline\Scripts\python.exe"
}
if (-not $EvidenceRoot) {
    $EvidenceRoot = Join-Path $repoRoot "artifacts\poc-02\windows-11\python-validation"
}

$dataRoot = Join-Path $RuntimeRoot "data"
$pgCtl = Join-Path $RuntimeRoot "pgsql\bin\pg_ctl.exe"
$runtimeLogPath = Join-Path $RuntimeRoot "postgresql.log"
$logPath = Join-Path $EvidenceRoot "postgresql.log"
$validationLog = Join-Path $EvidenceRoot "validation.log"
$resultPath = Join-Path $EvidenceRoot "result.json"
$validationScript = Join-Path $pocRoot "python\validate_database.py"

foreach ($requiredFile in @($PythonExecutable, $pgCtl, $validationScript, (Join-Path $dataRoot "PG_VERSION"))) {
    if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
        throw "Required Python validation input not found: $requiredFile"
    }
}
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
    throw "Port $Port is already in use"
}

New-Item -ItemType Directory -Force -Path $EvidenceRoot | Out-Null
$started = $false
try {
    & $pgCtl -D $dataRoot -l $runtimeLogPath -w start
    if ($LASTEXITCODE -ne 0) { throw "pg_ctl start failed with exit code $LASTEXITCODE" }
    $started = $true

    & $PythonExecutable $validationScript --port $Port --output $resultPath 2>&1 |
        Tee-Object -FilePath $validationLog
    if ($LASTEXITCODE -ne 0) { throw "Python database validation failed with exit code $LASTEXITCODE" }

    $result = Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
    if ($result.status -ne "PASS") { throw "Python database validation did not report PASS" }
} finally {
    if ($started) { & $pgCtl -D $dataRoot -m fast -w stop | Out-Null }
    if (Test-Path -LiteralPath $runtimeLogPath -PathType Leaf) {
        Copy-Item -LiteralPath $runtimeLogPath -Destination $logPath -Force
    }
}
