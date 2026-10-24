param(
    [string]$OutputDirectory = "artifacts/poc-08/windows-server-2025"
)

$ErrorActionPreference = "Stop"
$pocRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$repositoryRoot = [IO.Path]::GetFullPath((Join-Path $pocRoot "..\.."))
$outputRoot = [IO.Path]::GetFullPath($OutputDirectory)
$stageRoot = Join-Path $outputRoot "bundle-stage"
$archivePath = Join-Path $outputRoot "poc-08-windows-server-bundle.zip"

$repositoryPrefix = $repositoryRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
$outputPrefix = $outputRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
if (-not $outputRoot.StartsWith($repositoryPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "OutputDirectory must stay inside the repository workspace"
}
if (-not $stageRoot.StartsWith($outputPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Bundle staging path escaped the requested output directory"
}

if (Test-Path -LiteralPath $stageRoot) { Remove-Item -LiteralPath $stageRoot -Recurse -Force }
if (Test-Path -LiteralPath $archivePath) { Remove-Item -LiteralPath $archivePath -Force }
[IO.Directory]::CreateDirectory($stageRoot) | Out-Null
$target = Join-Path $stageRoot "poc-08-plugin-host"
[IO.Directory]::CreateDirectory($target) | Out-Null

foreach ($directory in @("src", "fixtures", "tests")) {
    Copy-Item -LiteralPath (Join-Path $pocRoot $directory) -Destination (Join-Path $target $directory) -Recurse
}
[IO.Directory]::CreateDirectory((Join-Path $target "scripts")) | Out-Null
Copy-Item -LiteralPath (Join-Path $pocRoot "scripts\run_validation.py") -Destination (Join-Path $target "scripts\run_validation.py")

Get-ChildItem -LiteralPath $stageRoot -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
Get-ChildItem -LiteralPath $stageRoot -Recurse -File -Filter "*.pyc" | Remove-Item -Force

$files = @(
    Get-ChildItem -LiteralPath $stageRoot -Recurse -File | Sort-Object FullName | ForEach-Object {
        [ordered]@{
            path = $_.FullName.Substring($stageRoot.Length + 1).Replace("\", "/")
            size_bytes = $_.Length
            sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    }
)
[ordered]@{
    schema_version = "poc08.bundle.v1"
    target = "Windows Server 2025 x86-64"
    file_count = $files.Count
    files = $files
} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $stageRoot "bundle-manifest.json") -Encoding UTF8

Compress-Archive -Path (Join-Path $stageRoot "*") -DestinationPath $archivePath -CompressionLevel Optimal
[ordered]@{
    archive = $archivePath
    size_bytes = (Get-Item -LiteralPath $archivePath).Length
    sha256 = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    file_count = $files.Count
} | ConvertTo-Json
