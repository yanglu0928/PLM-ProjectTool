param(
    [string]$BundleRoot = "C:\POC-01\bundle",
    [string]$OutputPath = $(Join-Path ([Environment]::GetFolderPath("MyDocuments")) "poc-01-windows-server-2025-evidence.zip")
)

$ErrorActionPreference = "Stop"
$evidenceRoot = Join-Path $BundleRoot "poc\poc-01-python-313-dependencies\evidence"
if (-not (Test-Path -LiteralPath $evidenceRoot -PathType Container)) {
    throw "Evidence directory not found"
}
if (Test-Path -LiteralPath $OutputPath) {
    Remove-Item -LiteralPath $OutputPath -Force
}
Compress-Archive -Path (Join-Path $evidenceRoot "*") -DestinationPath $OutputPath -CompressionLevel Optimal
