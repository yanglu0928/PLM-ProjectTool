$ErrorActionPreference = 'Stop'
$pg = 'D:\POC-02\postgresql-18.6\pgsql\bin'
$root = 'D:\PLM-Test-Temp'
$python = Join-Path $PSScriptRoot '..\..\apps\backend\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath (Join-Path $pg 'pg_ctl.exe')) -or
    -not (Test-Path -LiteralPath $python) -or
    -not (Test-Path -LiteralPath $root)) {
    throw 'Isolated PostgreSQL validation prerequisites unavailable'
}
$port = 55434
$probe = [System.Net.Sockets.TcpClient]::new()
try {
    $probe.Connect('127.0.0.1', $port)
    throw 'Validation port already in use; refusing to touch existing service'
} catch [System.Net.Sockets.SocketException] {
    # Port is free.
} finally {
    $probe.Dispose()
}
$run = Join-Path $root ('sur07a05-pg-' + [guid]::NewGuid().ToString('N'))
$resolvedRoot = [System.IO.Path]::GetFullPath($root).TrimEnd('\')
$resolvedRun = [System.IO.Path]::GetFullPath($run)
if (-not $resolvedRun.StartsWith($resolvedRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Temporary PostgreSQL target escaped intended directory'
}
New-Item -ItemType Directory -Path $resolvedRun | Out-Null
$data = Join-Path $resolvedRun 'data'
$log = Join-Path $resolvedRun 'postgresql.log'
$started = $false
try {
    & (Join-Path $pg 'initdb.exe') "--pgdata=$data" '--username=poc_admin' '--auth=trust' '--encoding=UTF8' '--locale=C' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'initdb failed' }
    $start = Start-Process -FilePath (Join-Path $pg 'pg_ctl.exe') -WindowStyle Hidden -PassThru `
        -ArgumentList "-D $data -l $log -o `"-h 127.0.0.1 -p $port`" -w start" `
        -RedirectStandardOutput (Join-Path $resolvedRun 'pg-start.out') `
        -RedirectStandardError (Join-Path $resolvedRun 'pg-start.err')
    if (-not $start.WaitForExit(60000) -or $start.ExitCode -ne 0) {
        throw 'pg_ctl start failed'
    }
    $started = $true
    & $python (Join-Path $PSScriptRoot 'verify.py')
    if ($LASTEXITCODE -ne 0) { throw 'SUR-07-A05 PostgreSQL validation failed' }
} finally {
    if ($started) {
        & (Join-Path $pg 'pg_ctl.exe') '-D' $data '-m' 'fast' '-w' 'stop' | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL stop failed; data preserved' }
    }
    & (Join-Path $pg 'pg_ctl.exe') '-D' $data 'status' *> $null
    if ($LASTEXITCODE -eq 0) {
        throw 'PostgreSQL remains running; data preserved'
    }
    if ($resolvedRun.StartsWith($resolvedRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $resolvedRun -Recurse -Force
    }
}
