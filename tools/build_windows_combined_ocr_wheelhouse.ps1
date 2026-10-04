param(
    [Parameter(Mandatory = $true)] [string]$PythonExe,
    [Parameter(Mandatory = $true)] [string]$BackendRunRoot,
    [Parameter(Mandatory = $true)] [string]$OcrRunRoot
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$allowedRoot = (Resolve-Path -LiteralPath (Join-Path $repoRoot 'artifacts\package-prep\windows11')).Path
$python = (Resolve-Path -LiteralPath $PythonExe).Path
$backend = (Resolve-Path -LiteralPath $BackendRunRoot).Path
$ocr = (Resolve-Path -LiteralPath $OcrRunRoot).Path
foreach ($inputRoot in @($backend, $ocr)) {
    if (-not $inputRoot.StartsWith($allowedRoot + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Wheelhouse input outside Windows11 package-prep rejected'
    }
}
$identity = & $python -c 'import json,platform,struct,sys; print(json.dumps({"version":sys.version_info[:2],"bits":struct.calcsize("P")*8,"system":platform.system(),"machine":platform.machine()}))'
if ($LASTEXITCODE -ne 0) { throw 'Python identity check failed' }
$runtime = $identity | ConvertFrom-Json
if ($runtime.version[0] -ne 3 -or $runtime.version[1] -ne 13 -or
    $runtime.bits -ne 64 -or $runtime.system -ne 'Windows' -or
    $runtime.machine -notin @('AMD64', 'x86_64')) {
    throw 'Windows Python 3.13 x64 is required'
}

function Read-PinnedWheels {
    param([string]$Root, [int]$ExpectedCount)
    $pins = @{}
    $wheelhouse = Join-Path $Root 'wheelhouse'
    foreach ($line in Get-Content -LiteralPath (Join-Path $Root 'sha256sums.txt')) {
        $match = [regex]::Match($line, '^([0-9a-f]{64})  ([A-Za-z0-9_.+-]+\.whl)$')
        if (-not $match.Success -or $pins.ContainsKey($match.Groups[2].Value)) {
            throw 'Wheel manifest rejected'
        }
        $pins[$match.Groups[2].Value] = $match.Groups[1].Value
    }
    $files = @(Get-ChildItem -LiteralPath $wheelhouse -File -Filter '*.whl')
    if ($pins.Count -ne $ExpectedCount -or $files.Count -ne $ExpectedCount) {
        throw 'Pinned wheel inventory count mismatch'
    }
    foreach ($file in $files) {
        if ($file.Attributes.HasFlag([IO.FileAttributes]::ReparsePoint) -or
            -not $pins.ContainsKey($file.Name) -or
            (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash.ToLowerInvariant() -cne $pins[$file.Name]) {
            throw "Pinned wheel source mismatch: $($file.Name)"
        }
    }
    return $pins
}

$backendSummary = Get-Content -LiteralPath (Join-Path $backend 'summary.json') -Raw | ConvertFrom-Json
$ocrSummary = Get-Content -LiteralPath (Join-Path $ocr 'summary.json') -Raw | ConvertFrom-Json
if ($backendSummary.status -ne 'WINDOWS11_BACKEND_WHEELHOUSE_INDEX_OFFLINE_PASS' -or
    $backendSummary.wheel_count -ne 93 -or
    $ocrSummary.status -ne 'WINDOWS11_OCRMYPDF_WHEELHOUSE_INDEX_OFFLINE_PASS' -or
    $ocrSummary.selected_wheel_count -ne 26 -or $ocrSummary.release_eligible -ne $false) {
    throw 'Wheelhouse summary rejected'
}
$backendPins = Read-PinnedWheels -Root $backend -ExpectedCount 93
$ocrPins = Read-PinnedWheels -Root $ocr -ExpectedCount 26
$backendNames = @{}
foreach ($name in $backendPins.Keys) {
    $project = ($name -split '-')[0].ToLowerInvariant()
    if ($backendNames.ContainsKey($project)) { throw 'Duplicate backend distribution' }
    $backendNames[$project] = $name
}
$newWheels = @()
$conflicts = @()
foreach ($name in $ocrPins.Keys) {
    $project = ($name -split '-')[0].ToLowerInvariant()
    if ($backendNames.ContainsKey($project)) {
        if ($backendNames[$project] -cne $name) {
            $conflicts += $project
        } elseif ($backendPins[$name] -cne $ocrPins[$name]) {
            throw "Same wheel name has different bytes: $name"
        }
    } else {
        $newWheels += $name
    }
}
if ($newWheels.Count -ne 13 -or $conflicts.Count -ne 1 -or $conflicts[0] -cne 'charset_normalizer' -or
    $backendNames['charset_normalizer'] -cne 'charset_normalizer-3.5.2-cp313-cp313-win_amd64.whl' -or
    -not $ocrPins.ContainsKey('charset_normalizer-3.5.1-cp313-cp313-win_amd64.whl')) {
    throw 'Unexpected backend/OCR dependency overlap; review CR-PKG-002'
}

$runName = 'combined-ocr-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 8)
$runRoot = Join-Path $allowedRoot $runName
$wheelhouse = Join-Path $runRoot 'wheelhouse'
New-Item -ItemType Directory -Path $wheelhouse | Out-Null
foreach ($name in $backendPins.Keys) {
    Copy-Item -LiteralPath (Join-Path $backend 'wheelhouse' $name) -Destination (Join-Path $wheelhouse $name)
}
foreach ($name in $newWheels) {
    Copy-Item -LiteralPath (Join-Path $ocr 'wheelhouse' $name) -Destination (Join-Path $wheelhouse $name)
}
$allPins = @{}
foreach ($name in $backendPins.Keys) { $allPins[$name] = $backendPins[$name] }
foreach ($name in $newWheels) { $allPins[$name] = $ocrPins[$name] }
$lines = @($allPins.Keys | Sort-Object | ForEach-Object {
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $wheelhouse $_)).Hash.ToLowerInvariant()
    if ($hash -cne $allPins[$_]) { throw "Combined wheel hash mismatch: $_" }
    "$hash  $_"
})
$lines | Set-Content -LiteralPath (Join-Path $runRoot 'sha256sums.txt') -Encoding ascii
$verifyRoot = Join-Path $runRoot 'verify-venv'
& $python -m venv $verifyRoot
if ($LASTEXITCODE -ne 0) { throw 'Fresh verification venv creation failed' }
$verifyPython = Join-Path $verifyRoot 'Scripts\python.exe'
$ownWheel = Join-Path $wheelhouse $backendSummary.backend_wheel
& $verifyPython -m pip install --disable-pip-version-check --no-index --find-links $wheelhouse $ownWheel ocrmypdf==17.12.1
if ($LASTEXITCODE -ne 0) { throw 'Combined no-index installation failed' }
& $verifyPython -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Combined dependency check failed' }
& $verifyPython -c 'from importlib import metadata; import plm_assistant,ocrmypdf,pikepdf,paddleocr; assert metadata.version("ocrmypdf")=="17.12.1"; assert metadata.version("charset-normalizer")=="3.5.2"'
if ($LASTEXITCODE -ne 0) { throw 'Combined import/version smoke failed' }

$summary = [ordered]@{
    status = 'WINDOWS11_COMBINED_OCR_WHEELHOUSE_INDEX_OFFLINE_PASS'
    release_eligible = $false
    wheel_count = $allPins.Count
    added_wheel_count = $newWheels.Count
    retained_backend_charset_normalizer = '3.5.2'
    verification = 'fresh-venv --no-index install, pip check, product/OCR imports'
    limits = 'No embedded runtime, native OCR system components, target ACL, physical air-gap or Release Gate validation'
}
$summary | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $runRoot 'summary.json') -Encoding utf8
Write-Output ($summary | ConvertTo-Json -Compress)
Write-Output "Artifacts: $runRoot"
