param(
    [Parameter(Mandatory = $true)]
    [string]$PythonExe
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$backend = Join-Path $repoRoot 'apps\backend'
$python = (Resolve-Path -LiteralPath $PythonExe).Path
$identity = & $python -c 'import json,platform,struct,sys; print(json.dumps({"version":sys.version_info[:2],"bits":struct.calcsize("P")*8,"system":platform.system(),"machine":platform.machine()}))'
if ($LASTEXITCODE -ne 0) { throw 'Python identity check failed' }
$runtime = $identity | ConvertFrom-Json
if ($runtime.version[0] -ne 3 -or $runtime.version[1] -ne 13 -or
    $runtime.bits -ne 64 -or $runtime.system -ne 'Windows' -or
    $runtime.machine -notin @('AMD64', 'x86_64')) {
    throw 'Windows Python 3.13 x64 is required'
}

$runName = 'backend-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 8)
$runRoot = Join-Path $repoRoot ('artifacts\package-prep\windows11\' + $runName)
$wheelhouse = Join-Path $runRoot 'wheelhouse'
$verifyRoot = Join-Path $runRoot 'verify-venv'
New-Item -ItemType Directory -Path $wheelhouse -Force | Out-Null

& $python -m pip wheel --disable-pip-version-check --no-deps --no-build-isolation --wheel-dir $wheelhouse $backend
if ($LASTEXITCODE -ne 0) { throw 'Backend wheel build failed' }
$ownWheels = @(Get-ChildItem -LiteralPath $wheelhouse -File -Filter 'plm_project_tool_backend-*.whl')
if ($ownWheels.Count -ne 1) { throw 'Exactly one backend wheel is required' }

& $python -m pip download --disable-pip-version-check --only-binary=:all: --dest $wheelhouse $ownWheels[0].FullName
if ($LASTEXITCODE -ne 0) { throw 'Wheel-only dependency resolution failed' }
$files = @(Get-ChildItem -LiteralPath $wheelhouse -File | Sort-Object Name)
if ($files.Count -lt 2 -or @($files | Where-Object Extension -ne '.whl').Count -ne 0) {
    throw 'Wheelhouse must contain only backend and dependency wheels'
}
$hashes = @($files | ForEach-Object {
    $digest = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    "$digest  $($_.Name)"
})
$hashes | Set-Content -LiteralPath (Join-Path $runRoot 'sha256sums.txt') -Encoding ascii

& $python -m venv $verifyRoot
if ($LASTEXITCODE -ne 0) { throw 'Clean verification venv creation failed' }
$verifyPython = Join-Path $verifyRoot 'Scripts\python.exe'
& $verifyPython -m pip install --disable-pip-version-check --no-index --find-links $wheelhouse $ownWheels[0].FullName
if ($LASTEXITCODE -ne 0) { throw 'Offline-index installation failed' }
& $verifyPython -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Offline-index dependency check failed' }
& $verifyPython -c 'import alembic,fastapi,fitz,openpyxl,paddle,paddleocr,paddlex,psycopg,sqlalchemy,uvicorn; import plm_assistant; from importlib import metadata; assert metadata.version("plm-project-tool-backend")==plm_assistant.__version__'
if ($LASTEXITCODE -ne 0) { throw 'Offline-index import smoke failed' }

$summary = [ordered]@{
    status = 'WINDOWS11_BACKEND_WHEELHOUSE_INDEX_OFFLINE_PASS'
    created_utc = (Get-Date).ToUniversalTime().ToString('o')
    python = '3.13 x64'
    wheel_count = $files.Count
    wheel_bytes = [int64](($files | Measure-Object Length -Sum).Sum)
    backend_wheel = $ownWheels[0].Name
    sha256_manifest = 'sha256sums.txt'
    verification = 'fresh-venv --no-index install, pip check, import smoke'
    limits = 'Not physical air-gap, Server2025, Debian13, full product or Release Gate validation'
}
$summary | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $runRoot 'summary.json') -Encoding utf8
Write-Output ($summary | ConvertTo-Json -Compress)
Write-Output "Artifacts: $runRoot"
