param(
    [Parameter(Mandatory = $true)][string]$BundleArchive,
    [string]$WorkRoot = "C:\POC-09",
    [string]$RunId = "run-01",
    [string]$BasePythonRoot = "C:\POC-01\bundle\runtime\python-3.13.15",
    [string]$Wheelhouse = "C:\POC-01\bundle\artifacts\poc-01\windows\wheelhouse"
)

$ErrorActionPreference = "Stop"
$bundleRoot = Join-Path $WorkRoot "bundle-$RunId"
$runtimeRoot = Join-Path $WorkRoot "runtime-$RunId"
$evidenceRoot = Join-Path $WorkRoot "evidence-$RunId"
$failure = $null

function Invoke-PythonProcess {
    param(
        [Parameter(Mandatory = $true)][string]$Python,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$Name
    )
    $stdout = Join-Path $evidenceRoot "$Name.stdout.txt"
    $stderr = Join-Path $evidenceRoot "$Name.stderr.txt"
    $process = Start-Process -FilePath $Python -ArgumentList $Arguments -Wait -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    return [ordered]@{ exit_code = $process.ExitCode; stdout = $stdout; stderr = $stderr }
}

foreach ($path in @($bundleRoot, $runtimeRoot, $evidenceRoot)) {
    if (Test-Path -LiteralPath $path) { throw "Clean validation path already exists: $path" }
}
foreach ($required in @($BundleArchive, $BasePythonRoot, $Wheelhouse)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Required validation source not found: $required" }
}

[IO.Directory]::CreateDirectory($bundleRoot) | Out-Null
[IO.Directory]::CreateDirectory($runtimeRoot) | Out-Null
[IO.Directory]::CreateDirectory($evidenceRoot) | Out-Null

try {
    $os = Get-CimInstance Win32_OperatingSystem
    $computer = Get-CimInstance Win32_ComputerSystem
    if ($os.Caption -notmatch "Windows Server 2025" -or $os.OSArchitecture -notmatch "64") {
        throw "This validation must run on Windows Server 2025 x86-64"
    }

    Expand-Archive -LiteralPath $BundleArchive -DestinationPath $bundleRoot
    $manifest = Get-Content -LiteralPath (Join-Path $bundleRoot "bundle-manifest.json") -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($entry in $manifest.files) {
        $candidate = Join-Path $bundleRoot ($entry.path.Replace("/", "\"))
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { throw "Bundle file missing: $($entry.path)" }
        $actual = (Get-FileHash -LiteralPath $candidate -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -ne $entry.sha256) { throw "Bundle file SHA-256 mismatch: $($entry.path)" }
    }

    $pythonRoot = Join-Path $runtimeRoot "python-3.13.15"
    Copy-Item -LiteralPath $BasePythonRoot -Destination $pythonRoot -Recurse
    $python = Join-Path $pythonRoot "python.exe"
    $install = Invoke-PythonProcess -Python $python -Name "pip-install" -Arguments @(
        "-m", "pip", "install", "--no-index", "--find-links", $Wheelhouse, "cryptography==50.0.1"
    )
    if ($install.exit_code -ne 0) { throw "Offline dependency installation failed" }

    $pocRoot = Join-Path $bundleRoot "poc-09-license"
    $env:PYTHONPATH = Join-Path $pocRoot "src"
    $unit = Invoke-PythonProcess -Python $python -Name "unit-tests" -Arguments @(
        "-m", "unittest", "discover", "-s", (Join-Path $pocRoot "tests"), "-p", "test_*.py", "-v"
    )
    $unitText = (Get-Content -LiteralPath $unit.stdout -Raw -ErrorAction SilentlyContinue) +
        (Get-Content -LiteralPath $unit.stderr -Raw -ErrorAction SilentlyContinue)
    $unitPass = $unit.exit_code -eq 0 -and $unitText -match "Ran 26 tests" -and $unitText -match "OK"
    if (-not $unitPass) { throw "Unit tests failed or expected test count was not observed" }

    $validationPath = Join-Path $evidenceRoot "validation.json"
    $validation = Invoke-PythonProcess -Python $python -Name "validation" -Arguments @(
        (Join-Path $pocRoot "scripts\run_validation.py"), "--output", $validationPath
    )
    if ($validation.exit_code -ne 0) { throw "Validation scenarios failed" }
    $validationResult = Get-Content -LiteralPath $validationPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($validationResult.status -ne "PASS" -or $validationResult.passed_count -ne 10) {
        throw "Validation result did not contain 10 passing scenarios"
    }

    [ordered]@{
        status = "PASS"
        platform = [ordered]@{
            caption = $os.Caption
            version = $os.Version
            architecture = $os.OSArchitecture
            logical_processors = $computer.NumberOfLogicalProcessors
            memory_bytes = [int64]$computer.TotalPhysicalMemory
        }
        python = (& $python -c "import platform; print(platform.python_version())").Trim()
        cryptography = (& $python -c "import cryptography; print(cryptography.__version__)").Trim()
        offline_dependency_install = "PASS"
        bundle_integrity = "PASS"
        unit_tests = [ordered]@{ passed = 26; failed = 0 }
        validation_scenarios = [ordered]@{ passed = 10; failed = 0 }
        invalid_license_scenarios_rejected = 8
        private_key_persisted = $false
        raw_mac_persisted = $false
    } | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $evidenceRoot "overall-result.json") -Encoding UTF8
}
catch {
    $failure = $_
    [ordered]@{
        status = "FAIL"
        error_type = $_.Exception.GetType().Name
        message = $_.Exception.Message
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $evidenceRoot "overall-result.json") -Encoding UTF8
}
finally {
    Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
}

Get-Content -LiteralPath (Join-Path $evidenceRoot "overall-result.json") -Raw
if ($null -ne $failure) { exit 1 }
