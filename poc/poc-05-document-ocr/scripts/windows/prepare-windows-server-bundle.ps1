param(
    [Parameter(Mandatory = $true)]
    [string]$OutputRoot,
    [string]$PythonExecutable = "D:\AI工具\PLM项目实施辅助工具\.poc-runtime\poc-01\windows-offline\Scripts\python.exe",
    [string]$DetectionModelDir = "$env:USERPROFILE\.paddlex\official_models\PP-OCRv5_mobile_det",
    [string]$RecognitionModelDir = "$env:USERPROFILE\.paddlex\official_models\PP-OCRv5_mobile_rec"
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..\..")
$pocRoot = Join-Path $repoRoot "poc\poc-05-document-ocr"
$stagingRoot = Join-Path $OutputRoot "staging"
$archivePath = Join-Path $OutputRoot "poc-05-windows-server-bundle.zip"

if (Test-Path -LiteralPath $stagingRoot) {
    throw "Staging directory already exists: $stagingRoot"
}
if (Test-Path -LiteralPath $archivePath) {
    throw "Bundle archive already exists: $archivePath"
}
foreach ($required in @($PythonExecutable, $DetectionModelDir, $RecognitionModelDir)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required bundle source not found: $required"
    }
}

New-Item -ItemType Directory -Force -Path $stagingRoot | Out-Null
$targetPoc = Join-Path $stagingRoot "poc\poc-05-document-ocr"
New-Item -ItemType Directory -Force -Path $targetPoc | Out-Null
foreach ($file in @("README.md", "acceptance-matrix.md", "fixture-spec.json", "requirements.txt")) {
    Copy-Item -LiteralPath (Join-Path $pocRoot $file) -Destination (Join-Path $targetPoc $file)
}
foreach ($directory in @("input", "schema", "src", "tests")) {
    Copy-Item -LiteralPath (Join-Path $pocRoot $directory) -Destination $targetPoc -Recurse
}
$targetScripts = Join-Path $targetPoc "scripts"
New-Item -ItemType Directory -Force -Path (Join-Path $targetScripts "windows") | Out-Null
Copy-Item -LiteralPath (Join-Path $pocRoot "scripts\validate_corpus.py") -Destination $targetScripts
Copy-Item -LiteralPath (Join-Path $pocRoot "scripts\windows\run-windows-server-validation.ps1") -Destination (Join-Path $targetScripts "windows")

$compatSource = Join-Path $repoRoot "poc\poc-01-python-313-dependencies\scripts\compat"
$compatTarget = Join-Path $stagingRoot "poc\poc-01-python-313-dependencies\scripts\compat"
New-Item -ItemType Directory -Force -Path $compatTarget | Out-Null
Copy-Item -LiteralPath (Join-Path $compatSource "sitecustomize.py") -Destination $compatTarget
Copy-Item -LiteralPath (Join-Path $compatSource "ocrmypdf_windows_compat.py") -Destination $compatTarget

$modelsRoot = Join-Path $stagingRoot "models"
New-Item -ItemType Directory -Force -Path $modelsRoot | Out-Null
Copy-Item -LiteralPath $DetectionModelDir -Destination $modelsRoot -Recurse
Copy-Item -LiteralPath $RecognitionModelDir -Destination $modelsRoot -Recurse

$wheelhouse = Join-Path $stagingRoot "wheelhouse"
New-Item -ItemType Directory -Force -Path $wheelhouse | Out-Null
& $PythonExecutable -m pip download --only-binary=:all: --dest $wheelhouse "jsonschema==4.26.0"
if ($LASTEXITCODE -ne 0) {
    throw "jsonschema wheel download failed"
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
    schema_version = "poc-05-offline-bundle.v1"
    target = "Windows Server 2025 x86-64"
    jsonschema_version = "4.26.0"
    file_count = @($manifestFiles).Count
    files = @($manifestFiles)
} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $stagingRoot "manifest.json") -Encoding UTF8

New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
Compress-Archive -Path (Join-Path $stagingRoot "*") -DestinationPath $archivePath -CompressionLevel Optimal
[ordered]@{
    archive = $archivePath
    size_bytes = (Get-Item -LiteralPath $archivePath).Length
    sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $archivePath).Hash.ToLowerInvariant()
} | ConvertTo-Json
