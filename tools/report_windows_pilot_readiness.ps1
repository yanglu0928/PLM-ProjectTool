[CmdletBinding()]
param(
    [string]$RegisterPath
)
$ErrorActionPreference = "Stop"
$payloadRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$packageRoot = Split-Path -Parent $payloadRoot
$python = Join-Path $packageRoot "payload\runtime\python\python.exe"
$reportTool = Join-Path $packageRoot "payload\tools\windows_pilot_readiness_report.py"
$manifest = Join-Path $packageRoot "manifest.json"
if (-not $RegisterPath) {
    $RegisterPath = Join-Path (Split-Path -Parent $packageRoot) "pilot-input-register.json"
}
if (-not (Test-Path -LiteralPath $python -PathType Leaf) -or
    -not (Test-Path -LiteralPath $reportTool -PathType Leaf) -or
    -not (Test-Path -LiteralPath $manifest -PathType Leaf)) {
    [Console]::Error.WriteLine("Pilot readiness diagnostic inputs are unavailable.")
    exit 2
}
& $python -I -B $reportTool --manifest $manifest --register $RegisterPath
exit $LASTEXITCODE
