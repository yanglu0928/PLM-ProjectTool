param(
    [string]$BundleRoot = "C:\POC-01\bundle"
)

$ErrorActionPreference = "Stop"
$pocRoot = Join-Path $BundleRoot "poc\poc-01-python-313-dependencies"
$installer = Join-Path $BundleRoot "artifacts\poc-01\windows\installers\python-3.13.15-amd64.exe"
$embeddedPackage = Join-Path $BundleRoot "artifacts\poc-01\windows\installers\python-3.13.15-embed-amd64.zip"
$pythonRoot = Join-Path $BundleRoot "runtime\python-3.13.15"
$python = Join-Path $pythonRoot "python.exe"
$wheelhouse = Join-Path $BundleRoot "artifacts\poc-01\windows\wheelhouse"
$statusPath = Join-Path $pocRoot "evidence\windows-server-2025\guest-validation-status.json"

$statusDirectory = Split-Path -Parent $statusPath
New-Item -ItemType Directory -Force -Path $statusDirectory | Out-Null
$pythonMode = "installed"
$installerExitCode = $null
$embeddedPackageSha256 = "d1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf"

try {
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        if (Test-Path -LiteralPath $installer -PathType Leaf) {
            New-Item -ItemType Directory -Force -Path $pythonRoot | Out-Null
            $arguments = @(
                '/quiet',
                'InstallAllUsers=0',
                "TargetDir=$pythonRoot",
                'Include_launcher=0',
                'Include_test=0',
                'Include_pip=1',
                'PrependPath=0',
                'Shortcuts=0'
            )
            $process = Start-Process -FilePath $installer -ArgumentList $arguments -Wait -PassThru
            $installerExitCode = $process.ExitCode
        }

        if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
            if (-not (Test-Path -LiteralPath $embeddedPackage -PathType Leaf)) {
                throw "Python is unavailable and no embedded package is available"
            }
            $actualEmbeddedHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $embeddedPackage).Hash.ToLowerInvariant()
            if ($actualEmbeddedHash -ne $embeddedPackageSha256) {
                throw "Embedded Python package SHA-256 mismatch"
            }

            if (Test-Path -LiteralPath $pythonRoot) {
                Remove-Item -LiteralPath $pythonRoot -Recurse -Force
            }
            New-Item -ItemType Directory -Force -Path $pythonRoot | Out-Null
            Expand-Archive -LiteralPath $embeddedPackage -DestinationPath $pythonRoot -Force
            $pthFile = Join-Path $pythonRoot "python313._pth"
            $pthLines = Get-Content -LiteralPath $pthFile
            $pthLines = $pthLines | ForEach-Object {
                if ($_ -eq "#import site") { "import site" } else { $_ }
            }
            $pthLines += "Lib\site-packages"
            Set-Content -LiteralPath $pthFile -Value $pthLines -Encoding ASCII

            $sitePackages = Join-Path $pythonRoot "Lib\site-packages"
            New-Item -ItemType Directory -Force -Path $sitePackages | Out-Null
            $pipWheel = Get-ChildItem -LiteralPath $wheelhouse -Filter "pip-*.whl" -File | Select-Object -First 1
            if (-not $pipWheel) {
                throw "pip wheel not found in the offline wheelhouse"
            }
            Add-Type -AssemblyName System.IO.Compression.FileSystem
            [System.IO.Compression.ZipFile]::ExtractToDirectory($pipWheel.FullName, $sitePackages)
            $pythonMode = "embedded"
        }
    }

    $pythonVersion = (& $python --version 2>&1 | Out-String).Trim()
    if ($pythonVersion -ne "Python 3.13.15") {
        throw "Unexpected Python version: $pythonVersion"
    }
    if (Test-Path -LiteralPath (Join-Path $pythonRoot "python313._pth") -PathType Leaf) {
        $pythonMode = "embedded"
    }

    $offlineScript = Join-Path $pocRoot "scripts\windows\run-offline-validation.ps1"
    $offlineArguments = @{
        WheelhousePath = $wheelhouse
        PythonLauncher = $python
        PythonTag = ""
        EvidencePlatform = "windows-server-2025"
    }
    if ($pythonMode -eq "embedded") {
        $offlineArguments.UseExistingPython = $true
    }
    & $offlineScript @offlineArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Offline dependency validation failed with exit code $LASTEXITCODE"
    }

    $ocrScript = Join-Path $pocRoot "scripts\windows\run-ocr-validation.ps1"
    & $ocrScript -EvidencePlatform "windows-server-2025-ocr" -PythonLauncher $python
    if ($LASTEXITCODE -ne 0) {
        throw "OCR validation failed with exit code $LASTEXITCODE"
    }

    [ordered]@{
        status = "PASS"
        python_version = $pythonVersion
        python_mode = $pythonMode
        installer_exit_code = $installerExitCode
        offline_dependencies = "PASS"
        ocr_pdfa_deskew = "PASS"
        completed_at_utc = [DateTime]::UtcNow.ToString("o")
    } | ConvertTo-Json | Set-Content -LiteralPath $statusPath -Encoding UTF8
} catch {
    [ordered]@{
        status = "FAIL"
        error = $_.Exception.Message
        completed_at_utc = [DateTime]::UtcNow.ToString("o")
    } | ConvertTo-Json | Set-Content -LiteralPath $statusPath -Encoding UTF8
    throw
}
