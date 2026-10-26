$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$tempRoot = 'D:\PLM-Test-Temp'
$python = Join-Path $repo 'apps\backend\.venv\Scripts\python.exe'
$pgSource = 'D:\POC-02\postgresql-18.6\pgsql'
$vectorSource = Join-Path $repo 'artifacts\poc-02\windows\source\pgvector-0.8.6'
foreach ($required in @((Join-Path $pgSource 'bin\initdb.exe'), (Join-Path $pgSource 'bin\pg_ctl.exe'), (Join-Path $vectorSource 'vector.dll'), $tempRoot, $python)) {
  if (-not (Test-Path -LiteralPath $required)) { throw "Required Win11 isolated test input missing: $required" }
}
$root = [System.IO.Path]::GetFullPath($tempRoot).TrimEnd('\')
$run = [System.IO.Path]::GetFullPath((Join-Path $root ('plan-version-edge-' + [guid]::NewGuid().ToString('N'))))
if (-not $run.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Temporary target escaped D drive test root' }
New-Item -ItemType Directory -Path $run | Out-Null
$savedPath = $env:PATH; $savedPythonPath = $env:PYTHONPATH; $savedTemp = $env:TEMP; $savedTmp = $env:TMP
try {
  $env:PATH = "$($pgSource)\bin;$savedPath"
  $env:PYTHONPATH = Join-Path $repo 'apps\backend\src'
  $env:TEMP = $tempRoot; $env:TMP = $tempRoot
  $env:PLM_BROWSER_TEMP_ROOT = $tempRoot
  & $python (Join-Path $PSScriptRoot 'verify.py') --run-root $run
  if ($LASTEXITCODE -ne 0) { throw 'PlanVersion Edge/PostgreSQL verifier failed' }
} finally {
  $env:PATH = $savedPath; $env:PYTHONPATH = $savedPythonPath; $env:TEMP = $savedTemp; $env:TMP = $savedTmp
  Remove-Item Env:PLM_BROWSER_TEMP_ROOT -ErrorAction SilentlyContinue
  if ($run.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) { Remove-Item -LiteralPath $run -Recurse -Force }
}
