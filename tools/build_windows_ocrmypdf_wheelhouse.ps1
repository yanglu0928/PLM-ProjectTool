param(
    [Parameter(Mandatory = $true)] [string]$PythonExe,
    [Parameter(Mandatory = $true)] [string]$SourceWheelhouse,
    [Parameter(Mandatory = $true)] [string]$SourceManifest
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$python = (Resolve-Path -LiteralPath $PythonExe).Path
$source = (Resolve-Path -LiteralPath $SourceWheelhouse).Path
$manifest = (Resolve-Path -LiteralPath $SourceManifest).Path
$identity = & $python -c 'import json,platform,struct,sys; print(json.dumps({"version":sys.version_info[:2],"bits":struct.calcsize("P")*8,"system":platform.system(),"machine":platform.machine()}))'
if ($LASTEXITCODE -ne 0) { throw 'Python identity check failed' }
$runtime = $identity | ConvertFrom-Json
if ($runtime.version[0] -ne 3 -or $runtime.version[1] -ne 13 -or
    $runtime.bits -ne 64 -or $runtime.system -ne 'Windows' -or
    $runtime.machine -notin @('AMD64', 'x86_64')) {
    throw 'Windows Python 3.13 x64 is required'
}

$entries = @{}
foreach ($line in Get-Content -LiteralPath $manifest) {
    if ($line -cnotmatch '^([0-9a-f]{64})  ([A-Za-z0-9_.+-]+\.whl)$') {
        throw 'Source manifest format rejected'
    }
    $name = $Matches[2]
    if ($entries.ContainsKey($name)) { throw 'Duplicate source wheel name' }
    $entries[$name] = $Matches[1]
}
$sourceWheels = @(Get-ChildItem -LiteralPath $source -File -Filter '*.whl')
if ($entries.Count -ne 109 -or $sourceWheels.Count -ne $entries.Count -or
    -not $entries.ContainsKey('ocrmypdf-17.12.1-py3-none-any.whl') -or
    $entries['ocrmypdf-17.12.1-py3-none-any.whl'] -cne
    'd1fc83dd2b567011f10afdd7612576f13c40183cbf1d867f898b64bb62d5f515') {
    throw 'Pinned source wheel inventory rejected'
}
foreach ($wheel in $sourceWheels) {
    if (-not $entries.ContainsKey($wheel.Name) -or
        (Get-FileHash -Algorithm SHA256 -LiteralPath $wheel.FullName).Hash.ToLowerInvariant() -cne $entries[$wheel.Name]) {
        throw "Pinned source wheel hash mismatch: $($wheel.Name)"
    }
}

$runName = 'ocrmypdf-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 8)
$runRoot = Join-Path $repoRoot ('artifacts\package-prep\windows11\' + $runName)
$wheelhouse = Join-Path $runRoot 'wheelhouse'
$verifyRoot = Join-Path $runRoot 'verify-venv'
New-Item -ItemType Directory -Path $wheelhouse -Force | Out-Null

& $python -m pip download --disable-pip-version-check --no-index --only-binary=:all: --find-links $source --dest $wheelhouse ocrmypdf==17.12.1
if ($LASTEXITCODE -ne 0) { throw 'No-index OCRmyPDF dependency resolution failed' }
$selected = @(Get-ChildItem -LiteralPath $wheelhouse -File -Filter '*.whl' | Sort-Object Name)
if ($selected.Count -lt 2 -or @($selected | Where-Object { -not $entries.ContainsKey($_.Name) }).Count -ne 0) {
    throw 'Resolved wheel inventory rejected'
}
$hashes = @($selected | ForEach-Object {
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant()
    if ($hash -cne $entries[$_.Name]) { throw "Resolved wheel hash mismatch: $($_.Name)" }
    "$hash  $($_.Name)"
})
$hashes | Set-Content -LiteralPath (Join-Path $runRoot 'sha256sums.txt') -Encoding ascii

& $python -m venv $verifyRoot
if ($LASTEXITCODE -ne 0) { throw 'Fresh verification venv creation failed' }
$verifyPython = Join-Path $verifyRoot 'Scripts\python.exe'
& $verifyPython -m pip install --disable-pip-version-check --no-index --find-links $wheelhouse ocrmypdf==17.12.1
if ($LASTEXITCODE -ne 0) { throw 'No-index fresh installation failed' }
& $verifyPython -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Fresh installation dependency check failed' }
& $verifyPython -c 'from importlib import metadata; import ocrmypdf,pikepdf; assert metadata.version("ocrmypdf")=="17.12.1"'
if ($LASTEXITCODE -ne 0) { throw 'Fresh installation import smoke failed' }

$summary = [ordered]@{
    status = 'WINDOWS11_OCRMYPDF_WHEELHOUSE_INDEX_OFFLINE_PASS'
    release_eligible = $false
    python = '3.13 x64'
    source_wheel_count = $sourceWheels.Count
    selected_wheel_count = $selected.Count
    selected_wheel_bytes = [int64](($selected | Measure-Object Length -Sum).Sum)
    wheel_sha256_manifest = 'sha256sums.txt'
    verification = 'fresh-venv --no-index install, pip check, import smoke'
    limits = 'No system Tesseract/Ghostscript, embedded-runtime merge, physical air-gap, ACL, target OS or Release Gate claim'
}
$summary | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $runRoot 'summary.json') -Encoding utf8
Write-Output ($summary | ConvertTo-Json -Compress)
Write-Output "Artifacts: $runRoot"
