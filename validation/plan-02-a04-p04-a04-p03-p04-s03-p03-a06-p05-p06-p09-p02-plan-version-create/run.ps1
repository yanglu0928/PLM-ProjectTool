$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$pgBin = 'D:\POC-02\postgresql-18.6\pgsql\bin'
$tempRoot = 'D:\PLM-Test-Temp'
$python = Join-Path $repo 'apps\backend\.venv\Scripts\python.exe'
foreach ($required in @((Join-Path $pgBin 'initdb.exe'), (Join-Path $pgBin 'pg_ctl.exe'), $tempRoot, $python)) {
  if (-not (Test-Path -LiteralPath $required)) { throw "Required isolated PG18 input missing: $required" }
}
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
$listener.Start(); $port = ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port; $listener.Stop()
$root = [System.IO.Path]::GetFullPath($tempRoot).TrimEnd('\')
$run = [System.IO.Path]::GetFullPath((Join-Path $root ('plan-version-create-' + [guid]::NewGuid().ToString('N'))))
if (-not $run.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Temporary target escaped D drive test root' }
New-Item -ItemType Directory -Path $run | Out-Null
$data = Join-Path $run 'data'; $started = $false
$savedPath = $env:PATH; $savedPythonPath = $env:PYTHONPATH; $savedTemp = $env:TEMP; $savedTmp = $env:TMP
try {
  & (Join-Path $pgBin 'initdb.exe') "--pgdata=$data" '--username=poc_admin' '--auth=trust' '--encoding=UTF8' '--locale=C' | Out-Null
  if ($LASTEXITCODE -ne 0) { throw 'Isolated initdb failed' }
  $proc = Start-Process -FilePath (Join-Path $pgBin 'pg_ctl.exe') -WindowStyle Hidden -PassThru -ArgumentList "-D `"$data`" -l `"$(Join-Path $run 'postgresql.log')`" -o `"-h 127.0.0.1 -p $port`" -w start" -RedirectStandardOutput (Join-Path $run 'start.out') -RedirectStandardError (Join-Path $run 'start.err')
  if (-not $proc.WaitForExit(60000) -or $proc.ExitCode -ne 0) { throw 'Isolated PG18 failed to start' }
  $started = $true
  $env:PATH = "$pgBin;$savedPath"; $env:PYTHONPATH = Join-Path $repo 'apps\backend\src'; $env:TEMP = $tempRoot; $env:TMP = $tempRoot
  & $python (Join-Path $PSScriptRoot 'verify.py') --port $port
  if ($LASTEXITCODE -ne 0) { throw 'PlanVersion Create verifier failed' }
} finally {
  if ($started) { & (Join-Path $pgBin 'pg_ctl.exe') '-D' $data '-m' 'fast' '-w' 'stop' | Out-Null; if ($LASTEXITCODE -ne 0) { throw 'PG18 failed to stop cleanly; preserve temp data' } }
  & (Join-Path $pgBin 'pg_ctl.exe') '-D' $data 'status' *> $null
  if ($LASTEXITCODE -eq 0) { throw 'PG18 remains running; preserve temp data' }
  $env:PATH = $savedPath; $env:PYTHONPATH = $savedPythonPath; $env:TEMP = $savedTemp; $env:TMP = $savedTmp
  if ($run.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) { Remove-Item -LiteralPath $run -Recurse -Force }
}
