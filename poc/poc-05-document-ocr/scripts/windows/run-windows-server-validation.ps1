param(
    [Parameter(Mandatory = $true)]
    [string]$BundleArchive,
    [string]$WorkRoot = "C:\POC-05",
    [string]$RunId = "run-01",
    [string]$BasePythonRoot = "C:\POC-01\bundle\runtime\python-3.13.15",
    [string]$Poc01Artifacts = "C:\POC-01\bundle\artifacts\poc-01\windows"
)

$ErrorActionPreference = "Stop"
$bundleRoot = Join-Path $WorkRoot "bundle-$RunId"
$runtimeRoot = Join-Path $WorkRoot "runtime-$RunId"
$evidenceRoot = Join-Path $WorkRoot "evidence-$RunId"
$evidenceArchive = Join-Path $WorkRoot "evidence-$RunId.zip"
$failure = $null

foreach ($path in @($bundleRoot, $runtimeRoot, $evidenceRoot, $evidenceArchive)) {
    if (Test-Path -LiteralPath $path) {
        throw "Clean offline validation path already exists: $path"
    }
}
foreach ($required in @($BundleArchive, $BasePythonRoot, $Poc01Artifacts)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required validation source not found: $required"
    }
}

New-Item -ItemType Directory -Force -Path $bundleRoot, $runtimeRoot, $evidenceRoot | Out-Null
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
    $manifest = Get-Content -LiteralPath (Join-Path $bundleRoot "manifest.json") -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($entry in $manifest.files) {
        $candidate = Join-Path $bundleRoot ($entry.path.Replace("/", "\"))
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            throw "Bundle file missing: $($entry.path)"
        }
        $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $candidate).Hash.ToLowerInvariant()
        if ($actual -ne $entry.sha256) {
            throw "Bundle file SHA-256 mismatch: $($entry.path)"
        }
    }

    $pythonRoot = Join-Path $runtimeRoot "python-3.13.15"
    Copy-Item -LiteralPath $BasePythonRoot -Destination $pythonRoot -Recurse
    $python = Join-Path $pythonRoot "python.exe"
    & $python -m pip install --no-index --find-links (Join-Path $bundleRoot "wheelhouse") "jsonschema==4.26.0"
    if ($LASTEXITCODE -ne 0) {
        throw "Offline jsonschema installation failed"
    }

    $pocRoot = Join-Path $bundleRoot "poc\poc-05-document-ocr"
    $tesseract = Join-Path $Poc01Artifacts "tesseract-portable\tesseract.exe"
    $tessdata = Join-Path $Poc01Artifacts "tessdata-best"
    $ghostscript = Join-Path $Poc01Artifacts "ghostscript-10.08.0-portable\bin\gswin64c.exe"
    foreach ($required in @($tesseract, $tessdata, $ghostscript)) {
        if (-not (Test-Path -LiteralPath $required)) {
            throw "OCR runtime source not found: $required"
        }
    }

    $env:PYTHONPATH = Join-Path $pocRoot "src"
    $env:TESSERACT_EXE = $tesseract
    $env:TESSDATA_PREFIX = $tessdata
    $env:PADDLE_DET_MODEL_DIR = Join-Path $bundleRoot "models\PP-OCRv5_mobile_det"
    $env:PADDLE_REC_MODEL_DIR = Join-Path $bundleRoot "models\PP-OCRv5_mobile_rec"
    $env:PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK = "True"
    $env:PATH = "$(Split-Path -Parent $tesseract);$(Split-Path -Parent $ghostscript);$env:PATH"

    & $python (Join-Path $pocRoot "tests\test_parser_units.py")
    if ($LASTEXITCODE -ne 0) {
        throw "Parser unit tests failed"
    }
    & $python (Join-Path $pocRoot "scripts\validate_corpus.py") `
        --input-dir (Join-Path $pocRoot "input") `
        --evidence-dir $evidenceRoot `
        --runtime-dir (Join-Path $runtimeRoot "outputs")
    if ($LASTEXITCODE -ne 0) {
        throw "POC-05 corpus validation failed"
    }

    $validation = Get-Content -LiteralPath (Join-Path $evidenceRoot "validation-result.json") -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($validation.status -ne "PASS") {
        throw "POC-05 validation result was not PASS"
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
            bundle_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $BundleArchive).Hash.ToLowerInvariant()
            local_paddle_models = $true
            pip_no_index = $true
        }
        completed_at_utc = [DateTime]::UtcNow.ToString("o")
    } | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $evidenceRoot "offline-result.json") -Encoding UTF8
} catch {
    $failure = $_
    [ordered]@{
        status = "FAIL"
        error = $_.Exception.Message
        completed_at_utc = [DateTime]::UtcNow.ToString("o")
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $evidenceRoot "offline-result.json") -Encoding UTF8
} finally {
    Compress-Archive -Path (Join-Path $evidenceRoot "*") -DestinationPath $evidenceArchive -CompressionLevel Optimal
}

if ($failure) {
    throw $failure
}
Get-Content -LiteralPath (Join-Path $evidenceRoot "offline-result.json") -Raw
