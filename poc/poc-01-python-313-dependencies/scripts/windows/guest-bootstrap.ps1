param(
    [string]$ArchivePath = $(Join-Path ([Environment]::GetFolderPath("MyDocuments")) "poc-01-windows-server-2025.zip"),
    [string]$BundleRoot = "C:\POC-01\bundle",
    [string]$EvidenceArchivePath = $(Join-Path ([Environment]::GetFolderPath("MyDocuments")) "poc-01-windows-server-2025-evidence.zip"),
    [string]$BootstrapStatusPath = $(Join-Path ([Environment]::GetFolderPath("MyDocuments")) "poc-01-windows-server-2025-bootstrap-status.json")
)

$ErrorActionPreference = "Stop"
$status = "FAIL"
$errorMessage = $null

try {
    if (-not (Test-Path -LiteralPath $ArchivePath -PathType Leaf)) {
        throw "Validation archive not found"
    }

    New-Item -ItemType Directory -Force -Path $BundleRoot | Out-Null
    Expand-Archive -LiteralPath $ArchivePath -DestinationPath $BundleRoot -Force

    $validationScript = Join-Path $BundleRoot "poc\poc-01-python-313-dependencies\scripts\windows\guest-run-validation.ps1"
    if (-not (Test-Path -LiteralPath $validationScript -PathType Leaf)) {
        throw "Guest validation script not found after extraction"
    }

    & $validationScript -BundleRoot $BundleRoot
    $status = "PASS"
} catch {
    $errorMessage = $_.Exception.Message
} finally {
    $evidenceRoot = Join-Path $BundleRoot "poc\poc-01-python-313-dependencies\evidence"
    if (Test-Path -LiteralPath $evidenceRoot -PathType Container) {
        if (Test-Path -LiteralPath $EvidenceArchivePath) {
            Remove-Item -LiteralPath $EvidenceArchivePath -Force
        }
        Compress-Archive -Path (Join-Path $evidenceRoot "*") -DestinationPath $EvidenceArchivePath -CompressionLevel Optimal
    }

    [ordered]@{
        status = $status
        error = $errorMessage
        completed_at_utc = [DateTime]::UtcNow.ToString("o")
        evidence_archive = $EvidenceArchivePath
    } | ConvertTo-Json | Set-Content -LiteralPath $BootstrapStatusPath -Encoding UTF8
}

if ($status -ne "PASS") {
    exit 1
}
