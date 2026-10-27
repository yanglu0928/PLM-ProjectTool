[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$WorkRoot,
    [Parameter(Mandatory=$true)][string]$OutputRoot
)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Get-Sha256([string]$Path) {
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}
function Invoke-CheckedCurl([string]$Url, [string]$Destination) {
    & curl.exe --fail --location --retry 3 --retry-delay 2 --connect-timeout 30 --speed-limit 1024 --speed-time 30 --output $Destination $Url
    if ($LASTEXITCODE -ne 0) { throw "Download failed: $Url" }
}
function Assert-Input([string]$Path, [long]$Size, [string]$Sha) {
    $item = Get-Item -LiteralPath $Path
    if ($item.Length -ne $Size -or (Get-Sha256 $Path) -cne $Sha) {
        throw "Pinned source input mismatch: $([IO.Path]::GetFileName($Path))"
    }
}

$root = [IO.Path]::GetFullPath($WorkRoot)
$out = [IO.Path]::GetFullPath($OutputRoot)
[IO.Directory]::CreateDirectory($root) | Out-Null
[IO.Directory]::CreateDirectory($out) | Out-Null
if ((Get-ChildItem -LiteralPath $root -Force | Measure-Object).Count -ne 0) {
    throw "WorkRoot must be a fresh empty runner-owned directory"
}
$driveRoot = [IO.Path]::GetPathRoot($root)
$free = ([IO.DriveInfo]::new($driveRoot)).AvailableFreeSpace
if ($free -lt 3GB) { throw "Insufficient cloud runner disk space for the PostgreSQL component: $free bytes" }

$downloads = Join-Path $root "downloads"
$pgExtract = Join-Path $root "pg-binary"
$source = Join-Path $root "pgvector"
$evidence = Join-Path $root "build-evidence"
$payload = Join-Path $root "output"
[IO.Directory]::CreateDirectory($downloads) | Out-Null
[IO.Directory]::CreateDirectory($pgExtract) | Out-Null
[IO.Directory]::CreateDirectory($evidence) | Out-Null
[IO.Directory]::CreateDirectory($payload) | Out-Null
$pgZip = Join-Path $downloads "postgresql-18.6-1-windows-x64-binaries.zip"
$pgSourceZip = Join-Path $downloads "pgvector-0.8.6.zip"
Invoke-CheckedCurl "https://get.enterprisedb.com/postgresql/postgresql-18.6-1-windows-x64-binaries.zip" $pgZip
Assert-Input $pgZip 343808005 "fbe23da234ee31547bf8a36d29dfd81e82b849df2d2b78d2eecb43d360252f8c"
Invoke-CheckedCurl "https://github.com/pgvector/pgvector/archive/refs/tags/v0.8.6.zip" $pgSourceZip
Assert-Input $pgSourceZip 214357 "250f5f488a5e512c8781c338608dfac32ae34f97088970a1b5bb8f5be797caf8"

Expand-Archive -LiteralPath $pgZip -DestinationPath $pgExtract
$pgRootCandidates = @(Get-ChildItem -LiteralPath $pgExtract -Directory -Recurse -Filter pgsql | Where-Object { Test-Path (Join-Path $_.FullName "bin\pg_config.exe") })
if ($pgRootCandidates.Count -ne 1) { throw "EDB binary archive did not yield one pgsql runtime root" }
$pgRoot = $pgRootCandidates[0].FullName

& git.exe clone --quiet --branch v0.8.6 --depth 1 https://github.com/pgvector/pgvector.git $source
if ($LASTEXITCODE -ne 0) { throw "Could not clone the pinned pgvector tag" }
$commit = (& git.exe -C $source rev-parse HEAD | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $commit -ne "8ee86c96f0fd72390f890aa8a336fda6d3ab4c6c") {
    throw "pgvector source commit mismatch: $commit"
}

$vswhere = Join-Path "${env:ProgramFiles(x86)}" "Microsoft Visual Studio\Installer\vswhere.exe"
if (-not (Test-Path -LiteralPath $vswhere)) { throw "Visual Studio locator unavailable on runner" }
$vsRoot = (& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath | Select-Object -First 1).Trim()
if (-not $vsRoot -or -not (Test-Path (Join-Path $vsRoot "Common7\Tools\VsDevCmd.bat"))) {
    throw "MSVC AMD64 build tools unavailable on runner"
}
$env:PLM_PG18_BUILD_TOOLCHAIN = (Get-Item (Join-Path $vsRoot "Common7\Tools\VsDevCmd.bat")).Directory.Parent.Parent.FullName

$buildScript = Join-Path $PSScriptRoot "..\poc\poc-02-postgresql-18-pgvector\scripts\windows\build-pgvector.ps1"
& $buildScript -SourceRoot $source -PostgreSqlRoot $pgRoot -BuildToolsRoot $vsRoot -EvidenceRoot $evidence
if ($LASTEXITCODE -ne 0) { throw "pgvector source build failed" }

$python = (Get-Command python.exe -ErrorAction Stop).Source
$builder = Join-Path $PSScriptRoot "package_windows_pg18_rebuilt_candidate.py"
$summary = & $python $builder --downloads $downloads --pg-root $pgRoot --source-root $source --output-parent $payload
if ($LASTEXITCODE -ne 0) { throw "Fresh PG18 sidecar packaging failed" }
$summary | Set-Content -LiteralPath (Join-Path $out "pg18-rebuilt-summary.json") -Encoding utf8
$archives = @(Get-ChildItem -LiteralPath $payload -Filter "NOT-FOR-RELEASE-windows-pg18-pgvector-runtime.zip" -Recurse -File)
if ($archives.Count -ne 1) { throw "Expected exactly one rebuilt PG18 runtime sidecar" }
Copy-Item -LiteralPath $archives[0].FullName -Destination (Join-Path $out $archives[0].Name)
Get-FileHash -LiteralPath (Join-Path $out $archives[0].Name) -Algorithm SHA256 |
    Select-Object Algorithm,Hash,Path | ConvertTo-Json |
    Set-Content -LiteralPath (Join-Path $out "sidecar-sha256.json") -Encoding utf8
