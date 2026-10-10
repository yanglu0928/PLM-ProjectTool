param(
    [string]$PythonLauncher = "py",
    [string]$PythonTag = "-3.13"
)

$ErrorActionPreference = "Stop"
$pocRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$repoRoot = (Resolve-Path (Join-Path $pocRoot "..\..")).Path
$artifactRoot = Join-Path $repoRoot "artifacts\poc-01\windows"
$wheelhouse = Join-Path $artifactRoot "wheelhouse"
$requirements = Join-Path $pocRoot "requirements\all.txt"

New-Item -ItemType Directory -Force -Path $wheelhouse | Out-Null
& $PythonLauncher $PythonTag -m pip download --dest $wheelhouse -r $requirements
& $PythonLauncher $PythonTag -m pip download --dest $wheelhouse pip setuptools wheel
Get-ChildItem -LiteralPath $wheelhouse -File |
    Get-FileHash -Algorithm SHA256 |
    ForEach-Object { "$($_.Hash.ToLower())  $([IO.Path]::GetFileName($_.Path))" } |
    Set-Content -Encoding ascii (Join-Path $artifactRoot "sha256sums.txt")
Copy-Item -LiteralPath (Join-Path $pocRoot "requirements") -Destination (Join-Path $artifactRoot "requirements") -Recurse -Force
