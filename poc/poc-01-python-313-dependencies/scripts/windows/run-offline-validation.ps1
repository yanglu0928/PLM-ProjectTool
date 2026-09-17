param(
    [Parameter(Mandatory = $true)]
    [string]$WheelhousePath,
    [string]$PythonLauncher = "py",
    [string]$PythonTag = "-3.13",
    [string]$EvidencePlatform = "windows-server-2025"
)

$ErrorActionPreference = "Stop"
$pocRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$repoRoot = (Resolve-Path (Join-Path $pocRoot "..\..")).Path
$runtimeRoot = Join-Path $repoRoot ".poc-runtime\poc-01\windows-offline"
$evidenceRoot = Join-Path $pocRoot ("evidence\" + $EvidencePlatform)
$requirements = Join-Path $pocRoot "requirements\all.txt"
$collector = Join-Path $pocRoot "scripts\collect_environment.py"
$verifier = Join-Path $pocRoot "scripts\verify_imports.py"
$resolvedWheelhouse = (Resolve-Path $WheelhousePath).Path

New-Item -ItemType Directory -Force -Path $runtimeRoot, $evidenceRoot | Out-Null
& $PythonLauncher $PythonTag -m venv $runtimeRoot
$python = Join-Path $runtimeRoot "Scripts\python.exe"
& $python -m pip install --no-index --find-links $resolvedWheelhouse pip setuptools wheel 2>&1 |
    Tee-Object -FilePath (Join-Path $evidenceRoot "offline-bootstrap.txt")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python -m pip install --no-index --find-links $resolvedWheelhouse -r $requirements 2>&1 |
    Tee-Object -FilePath (Join-Path $evidenceRoot "offline-install.txt")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python $collector | Set-Content -Encoding utf8 (Join-Path $evidenceRoot "environment.json")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python $verifier | Tee-Object -FilePath (Join-Path $evidenceRoot "verification.json")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
