param(
    [Parameter(Mandatory = $true)]
    [string]$BundleArchive,
    [Parameter(Mandatory = $true)]
    [string]$SecretFile,
    [string]$WorkRoot = "C:\POC-04",
    [string]$RunId = "run-01",
    [string]$BasePythonRoot = "C:\POC-01\bundle\runtime\python-3.13.15"
)

$ErrorActionPreference = "Stop"
$bundleRoot = Join-Path $WorkRoot "bundle-$RunId"
$runtimeRoot = Join-Path $WorkRoot "runtime-$RunId"
$evidenceRoot = Join-Path $WorkRoot "evidence-$RunId"
$evidenceArchive = Join-Path $WorkRoot "evidence-$RunId.zip"
$failure = $null
$secretDeleted = $false

function Invoke-PythonProcess {
    param(
        [Parameter(Mandatory = $true)][string]$Python,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$Name
    )
    $stdout = Join-Path $runtimeRoot "$Name.stdout.txt"
    $stderr = Join-Path $runtimeRoot "$Name.stderr.txt"
    $process = Start-Process -FilePath $Python -ArgumentList $Arguments -Wait -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    return [ordered]@{
        exit_code = $process.ExitCode
        stdout = $stdout
        stderr = $stderr
    }
}

foreach ($path in @($bundleRoot, $runtimeRoot, $evidenceRoot, $evidenceArchive)) {
    if (Test-Path -LiteralPath $path) {
        throw "Clean validation path already exists: $path"
    }
}
foreach ($required in @($BundleArchive, $SecretFile, $BasePythonRoot)) {
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
    $install = Invoke-PythonProcess -Python $python -Name "pip-install" -Arguments @(
        "-m", "pip", "install", "--no-index", "--find-links", (Join-Path $bundleRoot "wheelhouse"),
        "-r", (Join-Path $bundleRoot "poc\poc-04-ai-gateway\requirements.txt")
    )
    if ($install.exit_code -ne 0) {
        throw "Offline dependency installation failed with exit code $($install.exit_code)"
    }

    $pocRoot = Join-Path $bundleRoot "poc\poc-04-ai-gateway"
    $env:PYTHONPATH = Join-Path $pocRoot "src"
    $unit = Invoke-PythonProcess -Python $python -Name "unit-tests" -Arguments @(
        "-m", "unittest", "discover", "-s", (Join-Path $pocRoot "tests"), "-v"
    )
    $unitText = (Get-Content -LiteralPath $unit.stdout -Raw -ErrorAction SilentlyContinue) +
        (Get-Content -LiteralPath $unit.stderr -Raw -ErrorAction SilentlyContinue)
    $unitPass = $unit.exit_code -eq 0 -and $unitText -match "Ran 11 tests" -and $unitText -match "OK"
    [ordered]@{
        status = if ($unitPass) { "PASS" } else { "FAIL" }
        exit_code = $unit.exit_code
        expected_test_count = 11
        secret_value_recorded = $false
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $evidenceRoot "unit-test-result.json") -Encoding UTF8
    if (-not $unitPass) {
        throw "Unit tests failed or expected count was not observed"
    }

    $mock = Invoke-PythonProcess -Python $python -Name "mock-validation" -Arguments @(
        (Join-Path $pocRoot "scripts\validate_gateway.py"), "--evidence-dir", $evidenceRoot
    )
    if ($mock.exit_code -ne 0) {
        throw "Deterministic gateway validation failed with exit code $($mock.exit_code)"
    }

    $invalidKey = Invoke-PythonProcess -Python $python -Name "invalid-key" -Arguments @(
        (Join-Path $pocRoot "scripts\probe_deepseek_invalid_key.py"),
        "--output", (Join-Path $evidenceRoot "live-invalid-key-result.json")
    )
    if ($invalidKey.exit_code -ne 0) {
        throw "Live invalid-key probe failed with exit code $($invalidKey.exit_code)"
    }

    $rawSecret = Get-Content -LiteralPath $SecretFile -Raw -Encoding UTF8
    $match = [regex]::Match($rawSecret, '(?im)^\s*DEEPSEEK_API_KEY\s*[:=]\s*(\S+)\s*$')
    if ($match.Success) { $apiKey = $match.Groups[1].Value.Trim() } else { $apiKey = $rawSecret.Trim() }
    if ([string]::IsNullOrWhiteSpace($apiKey) -or $apiKey -match '\s' -or $apiKey.Length -lt 16) {
        throw "DeepSeek secret file format is not recognized"
    }
    try {
        $env:DEEPSEEK_API_KEY = $apiKey
        $live = Invoke-PythonProcess -Python $python -Name "live-validation" -Arguments @(
            (Join-Path $pocRoot "scripts\validate_deepseek_live.py"),
            "--output", (Join-Path $evidenceRoot "live-validation-result.json")
        )
    } finally {
        Remove-Item Env:DEEPSEEK_API_KEY -ErrorAction SilentlyContinue
        $apiKey = $null
        $rawSecret = $null
        Remove-Item -LiteralPath $SecretFile -Force -ErrorAction SilentlyContinue
        $secretDeleted = -not (Test-Path -LiteralPath $SecretFile)
    }
    if ($live.exit_code -ne 0) {
        throw "Live DeepSeek validation failed with exit code $($live.exit_code)"
    }

    $validation = Get-Content -LiteralPath (Join-Path $evidenceRoot "validation-result.json") -Raw -Encoding UTF8 | ConvertFrom-Json
    $invalidKeyResult = Get-Content -LiteralPath (Join-Path $evidenceRoot "live-invalid-key-result.json") -Raw -Encoding UTF8 | ConvertFrom-Json
    $liveResult = Get-Content -LiteralPath (Join-Path $evidenceRoot "live-validation-result.json") -Raw -Encoding UTF8 | ConvertFrom-Json
    $overallPass = $validation.status -eq "PASS" -and $validation.passed_count -eq 11 -and
        $invalidKeyResult.status -eq "PASS" -and $liveResult.status -eq "PASS" -and $secretDeleted
    [ordered]@{
        status = if ($overallPass) { "PASS" } else { "FAIL" }
        platform = [ordered]@{
            caption = $os.Caption
            version = $os.Version
            build_number = $os.BuildNumber
            architecture = "x86-64"
            logical_processors = $computer.NumberOfLogicalProcessors
            memory_gb = [math]::Round($computer.TotalPhysicalMemory / 1GB, 2)
        }
        network = [ordered]@{
            physical_adapter_count = $physicalAdapters.Count
            connected_physical_adapter_count = $connectedAdapters.Count
            online_required_for_live_provider = $true
        }
        bundle_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $BundleArchive).Hash.ToLowerInvariant()
        unit_tests = "11/11"
        deterministic_scenarios = "11/11"
        live_invalid_key = $invalidKeyResult.status
        live_text_stream_structured = $liveResult.status
        secret_deleted = $secretDeleted
        secret_value_recorded = $false
        response_content_recorded = $false
        completed_at_utc = [DateTime]::UtcNow.ToString("o")
    } | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $evidenceRoot "overall-result.json") -Encoding UTF8
    if (-not $overallPass) {
        throw "POC-04 Windows Server validation did not satisfy all checks"
    }
} catch {
    $failure = $_
    Remove-Item Env:DEEPSEEK_API_KEY -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $SecretFile -Force -ErrorAction SilentlyContinue
    $secretDeleted = -not (Test-Path -LiteralPath $SecretFile)
    [ordered]@{
        status = "FAIL"
        error_type = $_.Exception.GetType().Name
        error = $_.Exception.Message
        secret_deleted = $secretDeleted
        secret_value_recorded = $false
        completed_at_utc = [DateTime]::UtcNow.ToString("o")
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $evidenceRoot "overall-result.json") -Encoding UTF8
} finally {
    Remove-Item Env:DEEPSEEK_API_KEY -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $SecretFile -Force -ErrorAction SilentlyContinue
    if (-not (Test-Path -LiteralPath $evidenceArchive)) {
        Compress-Archive -Path (Join-Path $evidenceRoot "*") -DestinationPath $evidenceArchive -CompressionLevel Optimal
    }
}

if ($failure) {
    throw $failure
}
Get-Content -LiteralPath (Join-Path $evidenceRoot "overall-result.json") -Raw
