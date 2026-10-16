param(
    [Parameter(Mandatory = $true)]
    [string]$BundleArchive,
    [string]$WorkRoot = "C:\POC-02",
    [string]$RunId = "run-01",
    [string]$PythonExecutable = "C:\POC-01\bundle\runtime\python-3.13.15\python.exe",
    [int]$Port = 55432
)

$ErrorActionPreference = "Stop"
$bundleRoot = Join-Path $WorkRoot "bundle-$RunId"
$runtimeRoot = Join-Path $WorkRoot "runtime-$RunId"
$evidenceRoot = Join-Path $WorkRoot "evidence-$RunId"
$evidenceArchive = Join-Path $WorkRoot "evidence-$RunId.zip"
$overallResult = Join-Path $evidenceRoot "overall-result.json"
$failure = $null

foreach ($path in @($bundleRoot, $runtimeRoot, $evidenceRoot, $evidenceArchive)) {
    if (Test-Path -LiteralPath $path) {
        throw "Clean offline validation path already exists: $path"
    }
}
if (-not (Test-Path -LiteralPath $BundleArchive -PathType Leaf)) {
    throw "Bundle archive not found: $BundleArchive"
}
if (-not (Test-Path -LiteralPath $PythonExecutable -PathType Leaf)) {
    throw "Verified Python 3.13 executable not found"
}

New-Item -ItemType Directory -Force -Path $bundleRoot, $evidenceRoot | Out-Null
try {
    $os = Get-CimInstance Win32_OperatingSystem
    $computer = Get-CimInstance Win32_ComputerSystem
    if ($os.Caption -notmatch "Windows Server 2025" -or $os.OSArchitecture -notmatch "64") {
        throw "This validation must run on Windows Server 2025 x86-64"
    }

    $physicalAdapters = @(Get-NetAdapter -Physical -ErrorAction SilentlyContinue)
    $connectedAdapters = @($physicalAdapters | Where-Object Status -eq "Up")
    if ($connectedAdapters.Count -ne 0) {
        throw "Offline validation requires all physical network adapters to be disconnected"
    }

    Expand-Archive -LiteralPath $BundleArchive -DestinationPath $bundleRoot
    $manifestPath = Join-Path $bundleRoot "manifest.json"
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    $runtimeArchive = Join-Path $bundleRoot $manifest.runtime_archive.name
    $runtimeArchiveHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $runtimeArchive).Hash.ToLowerInvariant()
    if ($runtimeArchiveHash -ne $manifest.runtime_archive.sha256) {
        throw "Offline runtime archive SHA-256 mismatch"
    }

    $pocRoot = Join-Path $bundleRoot "poc"
    $scriptsRoot = Join-Path $pocRoot "scripts\windows"
    & (Join-Path $scriptsRoot "run-portable-postgresql-smoke.ps1") `
        -PostgreSqlArchive $runtimeArchive -RuntimeRoot $runtimeRoot -Port $Port `
        -EvidenceRoot (Join-Path $evidenceRoot "portable-smoke")
    & (Join-Path $scriptsRoot "run-pgvector-smoke.ps1") `
        -RuntimeRoot $runtimeRoot -Port $Port `
        -EvidenceRoot (Join-Path $evidenceRoot "pgvector-smoke")
    & (Join-Path $scriptsRoot "run-python-validation.ps1") `
        -PythonExecutable $PythonExecutable -RuntimeRoot $runtimeRoot -Port $Port `
        -EvidenceRoot (Join-Path $evidenceRoot "python-validation")
    & (Join-Path $scriptsRoot "run-backup-restore.ps1") `
        -RuntimeRoot $runtimeRoot -Port $Port `
        -EvidenceRoot (Join-Path $evidenceRoot "backup-restore")

    $componentResults = @(
        Join-Path $evidenceRoot "portable-smoke\result.json"
        Join-Path $evidenceRoot "pgvector-smoke\result.json"
        Join-Path $evidenceRoot "python-validation\result.json"
        Join-Path $evidenceRoot "backup-restore\result.json"
    )
    foreach ($resultFile in $componentResults) {
        $component = Get-Content -LiteralPath $resultFile -Raw | ConvertFrom-Json
        if ($component.status -ne "PASS") {
            throw "Component did not report PASS: $resultFile"
        }
    }

    [ordered]@{
        status = "PASS"
        platform = [ordered]@{
            caption = $os.Caption
            version = $os.Version
            build_number = $os.BuildNumber
            architecture = "x86-64"
            logical_processors = $computer.NumberOfLogicalProcessors
            memory_gb = [math]::Round($computer.TotalPhysicalMemory / 1GB, 2)
        }
        offline = [ordered]@{
            physical_adapter_count = $physicalAdapters.Count
            connected_physical_adapter_count = $connectedAdapters.Count
            runtime_archive_sha256 = $runtimeArchiveHash
        }
        postgresql_version = "18.6"
        pgvector_version = "0.8.6"
        completed_at_utc = [DateTime]::UtcNow.ToString("o")
    } | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $overallResult -Encoding UTF8
} catch {
    $failure = $_
    [ordered]@{
        status = "FAIL"
        error = $_.Exception.Message
        completed_at_utc = [DateTime]::UtcNow.ToString("o")
    } | ConvertTo-Json | Set-Content -LiteralPath $overallResult -Encoding UTF8
} finally {
    if (Test-Path -LiteralPath $evidenceArchive) {
        Remove-Item -LiteralPath $evidenceArchive -Force
    }
    Compress-Archive -Path (Join-Path $evidenceRoot "*") -DestinationPath $evidenceArchive -CompressionLevel Optimal
}

if ($failure) {
    throw $failure
}
Get-Content -LiteralPath $overallResult -Raw
