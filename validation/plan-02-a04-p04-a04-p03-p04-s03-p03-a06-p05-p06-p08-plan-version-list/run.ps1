$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$pgBin = 'D:\POC-02\postgresql-18.6\pgsql\bin'
$tempRoot = 'D:\PLM-Test-Temp'
$python = Join-Path $repo 'apps\backend\.venv\Scripts\python.exe'
foreach ($required in @((Join-Path $pgBin 'initdb.exe'), (Join-Path $pgBin 'pg_ctl.exe'), $tempRoot, $python)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Required isolated PG18 input missing: $required" }
}
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
$listener.Start()
$port = ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port
$listener.Stop()
$resolvedRoot = [System.IO.Path]::GetFullPath($tempRoot).TrimEnd('\')
$resolvedRun = [System.IO.Path]::GetFullPath((Join-Path $resolvedRoot ('plan-version-list-' + [guid]::NewGuid().ToString('N'))))
if (-not $resolvedRun.StartsWith($resolvedRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Temporary PostgreSQL target escaped its intended root' }
New-Item -ItemType Directory -Path $resolvedRun | Out-Null
$data = Join-Path $resolvedRun 'data'
$log = Join-Path $resolvedRun 'postgresql.log'
$started = $false
$savedPythonPath = $env:PYTHONPATH
$savedPath = $env:PATH
try {
    & (Join-Path $pgBin 'initdb.exe') "--pgdata=$data" '--username=poc_admin' '--auth=trust' '--encoding=UTF8' '--locale=C' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Isolated initdb failed' }
    $start = Start-Process -FilePath (Join-Path $pgBin 'pg_ctl.exe') -WindowStyle Hidden -PassThru `
        -ArgumentList "-D `"$data`" -l `"$log`" -o `"-h 127.0.0.1 -p $port`" -w start" `
        -RedirectStandardOutput (Join-Path $resolvedRun 'pg-start.out') `
        -RedirectStandardError (Join-Path $resolvedRun 'pg-start.err')
    if (-not $start.WaitForExit(60000) -or $start.ExitCode -ne 0) { throw 'Isolated PG18 failed to start' }
    $started = $true
    $env:PYTHONPATH = Join-Path $repo 'apps\backend\src'
    $env:PATH = "$pgBin;$savedPath"
    & $python (Join-Path $PSScriptRoot 'verify.py') --port $port
    if ($LASTEXITCODE -ne 0) { throw 'PLAN_VERSION_LIST PG18 verifier failed' }
} finally {
    if ($started) {
        & (Join-Path $pgBin 'pg_ctl.exe') '-D' $data '-m' 'fast' '-w' 'stop' | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Isolated PostgreSQL did not stop cleanly; data preserved' }
    }
    & (Join-Path $pgBin 'pg_ctl.exe') '-D' $data 'status' *> $null
    if ($LASTEXITCODE -eq 0) { throw 'Isolated PostgreSQL remains running; data preserved' }
    $env:PYTHONPATH = $savedPythonPath
    $env:PATH = $savedPath
    if ($resolvedRun.StartsWith($resolvedRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { Remove-Item -LiteralPath $resolvedRun -Recurse -Force }
}
