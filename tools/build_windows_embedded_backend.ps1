param(
    [Parameter(Mandatory = $true)] [string]$RuntimeArchive,
    [Parameter(Mandatory = $true)] [string]$BackendRunRoot,
    [Parameter(Mandatory = $true)] [string]$BuilderPython
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$allowedRoot = (Resolve-Path -LiteralPath (Join-Path $repoRoot 'artifacts\package-prep\windows11')).Path
$runtimeSource = (Resolve-Path -LiteralPath $RuntimeArchive).Path
$backendRoot = (Resolve-Path -LiteralPath $BackendRunRoot).Path
$builder = (Resolve-Path -LiteralPath $BuilderPython).Path
foreach ($source in @($runtimeSource, $backendRoot)) {
    if (-not $source.StartsWith($allowedRoot + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Embedded build input outside Windows11 package-prep rejected'
    }
}
if ((Split-Path -Leaf $runtimeSource) -ne 'python-3.13.15-embed-amd64.zip' -or
    (Get-FileHash -LiteralPath $runtimeSource -Algorithm SHA256).Hash.ToLowerInvariant() -ne
    'd1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf') {
    throw 'Official embedded runtime SHA-256 mismatch'
}
$identity = & $builder -c 'import json,platform,struct,sys; print(json.dumps({"version":sys.version_info[:2],"bits":struct.calcsize("P")*8,"system":platform.system(),"machine":platform.machine()}))'
if ($LASTEXITCODE -ne 0) { throw 'Builder Python identity failed' }
$builderIdentity = $identity | ConvertFrom-Json
if ($builderIdentity.version[0] -ne 3 -or $builderIdentity.version[1] -ne 13 -or
    $builderIdentity.bits -ne 64 -or $builderIdentity.system -ne 'Windows' -or
    $builderIdentity.machine -notin @('AMD64', 'x86_64')) {
    throw 'Builder must be Windows Python 3.13 x64'
}
$summary = Get-Content -LiteralPath (Join-Path $backendRoot 'summary.json') -Raw | ConvertFrom-Json
if ($summary.status -ne 'WINDOWS11_BACKEND_WHEELHOUSE_INDEX_OFFLINE_PASS' -or
    $summary.wheel_count -ne 93) { throw 'Backend wheelhouse source summary rejected' }
$wheelhouse = Join-Path $backendRoot 'wheelhouse'
$lines = @(Get-Content -LiteralPath (Join-Path $backendRoot 'sha256sums.txt'))
$files = @(Get-ChildItem -LiteralPath $wheelhouse -File)
if ($lines.Count -ne 93 -or $files.Count -ne $lines.Count) {
    throw 'Backend wheelhouse count mismatch'
}
$names = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
foreach ($line in $lines) {
    $match = [regex]::Match($line, '^([0-9a-f]{64})  ([A-Za-z0-9_.+-]+\.whl)$')
    if (-not $match.Success -or -not $names.Add($match.Groups[2].Value)) {
        throw 'Backend wheel manifest rejected'
    }
    $item = Get-Item -LiteralPath (Join-Path $wheelhouse $match.Groups[2].Value) -ErrorAction Stop
    if ($item.Attributes.HasFlag([IO.FileAttributes]::ReparsePoint) -or
        (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash.ToLowerInvariant() -ne
        $match.Groups[1].Value) {
        throw 'Backend wheel SHA-256 mismatch'
    }
}
$ownWheels = @(Get-ChildItem -LiteralPath $wheelhouse -File -Filter 'plm_project_tool_backend-*.whl')
if ($ownWheels.Count -ne 1 -or $ownWheels[0].Name -ne $summary.backend_wheel) {
    throw 'Backend product wheel mismatch'
}

$runRoot = Join-Path $allowedRoot ('embedded-backend-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
$runtime = Join-Path $runRoot 'runtime'
$packages = Join-Path $runtime 'packages'
New-Item -ItemType Directory -Path $packages -Force | Out-Null
Add-Type -AssemblyName System.IO.Compression.FileSystem
[IO.Compression.ZipFile]::ExtractToDirectory($runtimeSource, $runtime)
@('python313.zip', '.', 'packages', '#import site') |
    Set-Content -LiteralPath (Join-Path $runtime 'python313._pth') -Encoding ascii

& $builder -m pip install --disable-pip-version-check --no-index --only-binary=:all: --ignore-installed `
    --no-compile --find-links $wheelhouse --target $packages $ownWheels[0].FullName
if ($LASTEXITCODE -ne 0) { throw 'Offline wheel vendoring failed' }
$embedded = Join-Path $runtime 'python.exe'
$smoke = & $embedded -I -c 'import importlib.util,json,sys; import alembic,fastapi,fitz,openpyxl,paddle,paddleocr,paddlex,psycopg,sqlalchemy,uvicorn; import plm_assistant; import plm_assistant.entrypoints.service_windows; from importlib import metadata; assert metadata.version("plm-project-tool-backend")==plm_assistant.__version__; print(json.dumps({"version":plm_assistant.__version__,"paths":sys.path,"prefix":sys.prefix,"pip_present":importlib.util.find_spec("pip") is not None}))'
if ($LASTEXITCODE -ne 0) { throw 'Embedded backend import smoke failed' }
$jsonLine = @($smoke | Where-Object { $_ -match '^\{"version":' } | Select-Object -Last 1)
if ($jsonLine.Count -ne 1) { throw 'Embedded backend smoke result missing' }
$verified = $jsonLine[0] | ConvertFrom-Json
if (@($verified.paths | Where-Object {
    -not [IO.Path]::GetFullPath($_).StartsWith($runtime + [IO.Path]::DirectorySeparatorChar,
        [StringComparison]::OrdinalIgnoreCase) -and
    -not [IO.Path]::GetFullPath($_).Equals($runtime, [StringComparison]::OrdinalIgnoreCase)
}).Count -ne 0) { throw 'Embedded backend import path escaped private runtime' }
$distributionCount = @(Get-ChildItem -LiteralPath $packages -Directory -Filter '*.dist-info').Count
if ($verified.pip_present -or
    -not [IO.Path]::GetFullPath($verified.prefix).Equals($runtime, [StringComparison]::OrdinalIgnoreCase) -or
    $distributionCount -ne $names.Count) {
    throw 'Embedded backend private distribution inventory mismatch'
}
$savedPath = $env:PATH
$savedPythonPath = $env:PYTHONPATH
try {
    $env:PATH = "$runtime;$env:WINDIR\System32;$env:WINDIR"
    Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    $cleanSmoke = & $embedded -I -c 'import fastapi,sqlalchemy,psycopg,paddle,paddleocr,paddlex,plm_assistant; import plm_assistant.entrypoints.service_windows; print("CLEAN_PATH_IMPORT_PASS")'
    if ($LASTEXITCODE -ne 0 -or @($cleanSmoke) -notcontains 'CLEAN_PATH_IMPORT_PASS') {
        throw 'Embedded backend clean PATH native import failed'
    }
} finally {
    $env:PATH = $savedPath
    if ($null -ne $savedPythonPath) { $env:PYTHONPATH = $savedPythonPath }
}
[ordered]@{
    status = 'WINDOWS11_EMBEDDED_BACKEND_IMPORT_PASS'
    release_eligible = $false
    python = '3.13.15 AMD64 official embed'
    product_version = $verified.version
    wheel_count = $names.Count
    installed_distribution_count = $distributionCount
    target_machine_pip_required = $false
    private_import_path = $true
    clean_path_import = $true
    run_root = $runRoot
} | ConvertTo-Json -Depth 4
