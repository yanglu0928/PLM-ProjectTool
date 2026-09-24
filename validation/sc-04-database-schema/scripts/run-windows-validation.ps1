param(
    [string]$PythonExecutable = "C:\Users\17231\AppData\Local\Python\pythoncore-3.13-64\python.exe",
    [string]$SitePackages = "",
    [string]$RuntimeRoot = "D:\POC-02\postgresql-18.6",
    [int]$Port = 55434,
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
$validationRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$repoRoot = (Resolve-Path (Join-Path $validationRoot "..\..")).Path
if (-not $SitePackages) {
    $SitePackages = Join-Path $repoRoot ".poc-runtime\poc-01\windows-offline\Lib\site-packages"
}
if (-not $OutputPath) {
    $OutputPath = Join-Path $validationRoot "evidence\windows-11\result.json"
}

$pgBin = Join-Path $RuntimeRoot "pgsql\bin"
$pgCtl = Join-Path $pgBin "pg_ctl.exe"
$dataRoot = Join-Path $RuntimeRoot "data"
$validationScript = Join-Path $validationRoot "validate_sc04.py"
$runtimeLog = Join-Path $env:TEMP "plm-sc04-postgresql.log"

foreach ($required in @($PythonExecutable, $SitePackages, $pgCtl, (Join-Path $dataRoot "PG_VERSION"), $validationScript)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "SC-04 required input not found: $required"
    }
}
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
    throw "SC-04 port $Port is already in use"
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $OutputPath) | Out-Null
$savedPythonPath = $env:PYTHONPATH
$savedPath = $env:PATH
$env:PYTHONPATH = "$SitePackages;$validationRoot"
$env:PATH = "$pgBin;$env:PATH"
$started = $false
try {
    & $pgCtl -D $dataRoot -l $runtimeLog -o "-p $Port" -w start
    if ($LASTEXITCODE -ne 0) { throw "SC-04 PostgreSQL start failed: $LASTEXITCODE" }
    $started = $true
    & $PythonExecutable $validationScript --port $Port --pg-bin $pgBin --output $OutputPath
    if ($LASTEXITCODE -ne 0) { throw "SC-04 validation failed: $LASTEXITCODE" }
    $result = Get-Content -LiteralPath $OutputPath -Raw | ConvertFrom-Json
    if ($result.status -ne "PASS") { throw "SC-04 result is not PASS" }
} finally {
    if ($started) {
        & $pgCtl -D $dataRoot -m fast -w stop | Out-Null
    }
    $env:PYTHONPATH = $savedPythonPath
    $env:PATH = $savedPath
    if (Test-Path -LiteralPath $runtimeLog) {
        Remove-Item -LiteralPath $runtimeLog -Force
    }
}
