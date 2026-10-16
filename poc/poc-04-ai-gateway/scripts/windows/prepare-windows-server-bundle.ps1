param(
    [Parameter(Mandatory = $true)]
    [string]$OutputRoot,
    [string]$Poc01Wheelhouse = "",
    [string]$JsonschemaWheelhouse = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..\..")
$pocRoot = Join-Path $repoRoot "poc\poc-04-ai-gateway"
if (-not [System.IO.Path]::IsPathRooted($OutputRoot)) {
    $OutputRoot = Join-Path $repoRoot $OutputRoot
}
$OutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
$stagingRoot = Join-Path $OutputRoot "staging"
$archivePath = Join-Path $OutputRoot "poc-04-windows-server-bundle.zip"

if ([string]::IsNullOrWhiteSpace($Poc01Wheelhouse)) {
    $Poc01Wheelhouse = Join-Path $repoRoot "artifacts\poc-01\windows\wheelhouse"
}

if (Test-Path -LiteralPath $stagingRoot) {
    throw "Staging directory already exists: $stagingRoot"
}
if (Test-Path -LiteralPath $archivePath) {
    throw "Bundle archive already exists: $archivePath"
}
if (-not (Test-Path -LiteralPath $Poc01Wheelhouse -PathType Container)) {
    throw "POC-01 wheelhouse not found: $Poc01Wheelhouse"
}
if ([string]::IsNullOrWhiteSpace($JsonschemaWheelhouse)) {
    $candidate = Get-ChildItem -LiteralPath (Join-Path $repoRoot "artifacts\poc-05\windows-server-2025") -Directory -Filter "bundle-*" |
        Sort-Object LastWriteTimeUtc |
        Select-Object -Last 1
    if (-not $candidate) {
        throw "No POC-05 Windows Server bundle found for jsonschema wheels"
    }
    $JsonschemaWheelhouse = Join-Path $candidate.FullName "staging\wheelhouse"
}
if (-not (Test-Path -LiteralPath $JsonschemaWheelhouse -PathType Container)) {
    throw "jsonschema wheelhouse not found: $JsonschemaWheelhouse"
}

New-Item -ItemType Directory -Force -Path $stagingRoot | Out-Null
$targetPoc = Join-Path $stagingRoot "poc\poc-04-ai-gateway"
New-Item -ItemType Directory -Force -Path $targetPoc | Out-Null
foreach ($file in @("README.md", "acceptance-matrix.md", "official-docs-snapshot.md", "requirements.txt")) {
    Copy-Item -LiteralPath (Join-Path $pocRoot $file) -Destination (Join-Path $targetPoc $file)
}
foreach ($directory in @("src", "tests")) {
    Copy-Item -LiteralPath (Join-Path $pocRoot $directory) -Destination $targetPoc -Recurse
}
$targetScripts = Join-Path $targetPoc "scripts"
New-Item -ItemType Directory -Force -Path (Join-Path $targetScripts "windows") | Out-Null
foreach ($script in @("validate_gateway.py", "validate_deepseek_live.py", "probe_deepseek_invalid_key.py")) {
    Copy-Item -LiteralPath (Join-Path $pocRoot "scripts\$script") -Destination $targetScripts
}
Copy-Item -LiteralPath (Join-Path $pocRoot "scripts\windows\run-windows-server-validation.ps1") -Destination (Join-Path $targetScripts "windows")

$wheelhouse = Join-Path $stagingRoot "wheelhouse"
New-Item -ItemType Directory -Force -Path $wheelhouse | Out-Null
$poc01Packages = @("anyio", "certifi", "h11", "httpcore", "httpx", "idna", "typing_extensions")
$schemaPackages = @("attrs", "jsonschema", "jsonschema_specifications", "referencing", "rpds_py")
foreach ($package in $poc01Packages) {
    $wheel = @(Get-ChildItem -LiteralPath $Poc01Wheelhouse -File -Filter "$package-*.whl")
    if ($wheel.Count -ne 1) {
        throw "Expected exactly one wheel for $package in $Poc01Wheelhouse, found $($wheel.Count)"
    }
    Copy-Item -LiteralPath $wheel[0].FullName -Destination $wheelhouse
}
foreach ($package in $schemaPackages) {
    $wheel = @(Get-ChildItem -LiteralPath $JsonschemaWheelhouse -File -Filter "$package-*.whl")
    if ($wheel.Count -ne 1) {
        throw "Expected exactly one wheel for $package in $JsonschemaWheelhouse, found $($wheel.Count)"
    }
    Copy-Item -LiteralPath $wheel[0].FullName -Destination $wheelhouse
}

$files = Get-ChildItem -LiteralPath $stagingRoot -File -Recurse | Sort-Object FullName
$manifestFiles = foreach ($file in $files) {
    [ordered]@{
        path = $file.FullName.Substring($stagingRoot.Length + 1).Replace("\", "/")
        size_bytes = $file.Length
        sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash.ToLowerInvariant()
    }
}
[ordered]@{
    schema_version = "poc-04-server-bundle.v1"
    target = "Windows Server 2025 x86-64"
    file_count = @($manifestFiles).Count
    files = @($manifestFiles)
} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $stagingRoot "manifest.json") -Encoding UTF8

Compress-Archive -Path (Join-Path $stagingRoot "*") -DestinationPath $archivePath -CompressionLevel Optimal
[ordered]@{
    archive = $archivePath
    size_bytes = (Get-Item -LiteralPath $archivePath).Length
    sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $archivePath).Hash.ToLowerInvariant()
    wheel_count = @(Get-ChildItem -LiteralPath $wheelhouse -File -Filter "*.whl").Count
} | ConvertTo-Json
