$ErrorActionPreference = "Stop"
function Get-Sha256Hex([string]$path) {
    $stream = $null
    $algorithm = $null
    try {
        $stream = [System.IO.File]::OpenRead($path)
        $algorithm = [System.Security.Cryptography.SHA256]::Create()
        $digest = $algorithm.ComputeHash($stream)
        return [System.BitConverter]::ToString($digest).Replace("-", "").ToLowerInvariant()
    }
    finally {
        if ($null -ne $stream) { $stream.Dispose() }
        if ($null -ne $algorithm) { $algorithm.Dispose() }
    }
}
function Test-StrictJsonBoolean($value, [bool]$expected) {
    return ($null -ne $value -and $value.GetType() -eq [bool] -and $value -eq $expected)
}
function Write-StartupFailure($manifest) {
    $message = "Packaged production startup blocked; trust prerequisites are not ready."
    $failureStage = "CHECK_INPUT_PATHS"
    $diagnosticProcess = $null
    try {
        if ($null -eq $manifest) { throw "manifest unavailable" }
        $packageRoot = Split-Path -Parent $PSScriptRoot
        $checksumsPath = Join-Path $packageRoot "payload-sha256sums.txt"
        $diagnosticPath = Join-Path $PSScriptRoot "check-startup.ps1"
        if (-not (Test-Path -LiteralPath $checksumsPath -PathType Leaf) -or
            -not (Test-Path -LiteralPath $diagnosticPath -PathType Leaf)) {
            throw "diagnostic package input unavailable"
        }
        $failureStage = "HASH_CHECKSUM_FILE"
        $checksumsDigest = Get-Sha256Hex $checksumsPath
        $failureStage = "CHECK_MANIFEST_HASH"
        if ($manifest.payload_sha256sums_sha256 -isnot [string] -or
            $manifest.payload_sha256sums_sha256 -cnotmatch "^[0-9a-f]{64}$" -or
            $checksumsDigest -cne $manifest.payload_sha256sums_sha256) {
            throw "diagnostic checksum inventory rejected"
        }
        $failureStage = "READ_CHECKSUMS"
        $entries = @(Get-Content -LiteralPath $checksumsPath -Encoding ASCII | Where-Object { $_ -cmatch "^[0-9a-f]{64}  payload/check-startup\.ps1$" })
        $failureStage = "MATCH_CHECKSUM_ENTRY"
        if ($entries.Count -ne 1) { throw "diagnostic checksum entry rejected" }
        $expectedDigest = [regex]::Match($entries[0], "^([0-9a-f]{64})  payload/check-startup\.ps1$").Groups[1].Value
        $failureStage = "HASH_DIAGNOSTIC"
        $actualDigest = Get-Sha256Hex $diagnosticPath
        if ($actualDigest -cne $expectedDigest) { throw "diagnostic script checksum mismatch" }

        $failureStage = "RESOLVE_PROCESS"
        $shell = Get-Command powershell.exe -CommandType Application -ErrorAction Stop | Select-Object -First 1
        $startInfo = New-Object System.Diagnostics.ProcessStartInfo
        $startInfo.FileName = $shell.Source
        $quotedDiagnosticPath = '"' + $diagnosticPath.Replace('"', '\"') + '"'
        $startInfo.Arguments = "-NoLogo -NoProfile -NonInteractive -File $quotedDiagnosticPath"
        $startInfo.UseShellExecute = $false
        $startInfo.CreateNoWindow = $true
        $startInfo.RedirectStandardOutput = $true
        $startInfo.RedirectStandardError = $true
        $diagnosticProcess = New-Object System.Diagnostics.Process
        $diagnosticProcess.StartInfo = $startInfo
        $failureStage = "START_PROCESS"
        if (-not $diagnosticProcess.Start()) { throw "diagnostic process did not start" }

        $stdoutTask = $diagnosticProcess.StandardOutput.ReadToEndAsync()
        $stderrTask = $diagnosticProcess.StandardError.ReadToEndAsync()
        $failureStage = "WAIT_PROCESS"
        if (-not $diagnosticProcess.WaitForExit(15000)) {
            try {
                $diagnosticProcess.Kill()
                $null = $diagnosticProcess.WaitForExit(5000)
            } catch {}
            throw "diagnostic process exceeded its 15 second limit"
        }
        $diagnosticProcess.WaitForExit()
        $failureStage = "READ_PROCESS_OUTPUT"
        $diagnosticText = $stdoutTask.GetAwaiter().GetResult()
        $diagnosticError = $stderrTask.GetAwaiter().GetResult()
        $diagnosticLines = @($diagnosticText -split "\r?\n" | Where-Object { $_.Length -gt 0 })
        $failureStage = "CHECK_PROCESS_CONTRACT"
        if ($diagnosticProcess.ExitCode -ne 2 -or
            $diagnosticError.Length -ne 0 -or
            $diagnosticLines.Count -ne 1) {
            throw "diagnostic command contract rejected"
        }
        $diagnosticText = $diagnosticLines[0]
        $failureStage = "PARSE_REPORT"
        $report = $diagnosticText | ConvertFrom-Json
        $failureStage = "VALIDATE_REPORT"
        if ($report.status -cne "BLOCKED" -or
            -not (Test-StrictJsonBoolean $report.release_eligible $false) -or
            -not (Test-StrictJsonBoolean $report.legal_clearance $false) -or
            $report.blocker_codes -isnot [System.Array] -or
            $report.messages -isnot [System.Array] -or
            $report.blocker_codes.Count -lt 1 -or
            $report.messages.Count -ne $report.blocker_codes.Count -or
            $diagnosticText -match "(?i)([A-Z]:\\|\\Users\\|PLM_[A-Z0-9_]+)") {
            throw "diagnostic report contract rejected"
        }
        foreach ($code in $report.blocker_codes) {
            if ($code -isnot [string] -or $code -cnotmatch "^[A-Z][A-Z0-9_]+$") {
                throw "diagnostic blocker code rejected"
            }
        }
        foreach ($messageText in $report.messages) {
            if ($messageText -isnot [string] -or $messageText.Length -gt 200) {
                throw "diagnostic message rejected"
            }
        }
        [Console]::Out.WriteLine($diagnosticText)
        $message = "Packaged production startup blocked; see BLOCKED diagnostics above."
    }
    catch {
        if ([Environment]::GetEnvironmentVariable("PLM_STARTUP_DIAGNOSTIC_TRACE") -ceq "A33") {
            [Console]::Error.WriteLine("A33_DIAGNOSTIC_STAGE:" + $failureStage)
        }
        $message = "Packaged production startup blocked; trust prerequisites are not ready."
    }
    finally {
        if ($null -ne $diagnosticProcess) { $diagnosticProcess.Dispose() }
    }
    [Console]::Error.WriteLine($message)
}
try {
    $payloadRoot = Split-Path -Parent $PSScriptRoot
    $manifestPath = Join-Path $payloadRoot "manifest.json"
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        throw "manifest missing"
    }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $startup = $manifest.startup_preflight
    if (
        $manifest.kind -ne "WINDOWS_PARENT_PACKAGE_NON_RELEASE_CANDIDATE" -or
        -not (Test-StrictJsonBoolean $manifest.release_eligible $false) -or
        -not (Test-StrictJsonBoolean $manifest.legal_clearance $false) -or
        -not (Test-StrictJsonBoolean $startup.formal_startup_ready $true) -or
        -not (Test-StrictJsonBoolean $startup.packaged_product_public_key_resource_present $true) -or
        -not (Test-StrictJsonBoolean $startup.formal_license_trust_verified $true) -or
        $startup.database_credential_target_reference -isnot [string] -or
        $startup.database_credential_target_reference -ne "PLMProjectTool/Database" -or
        -not (Test-StrictJsonBoolean $startup.database_credential_reference_verified $true) -or
        -not (Test-StrictJsonBoolean $startup.service_identity_acl_verified $true) -or
        -not (Test-StrictJsonBoolean $startup.tls_certificate_configured $true) -or
        -not (Test-StrictJsonBoolean $startup.tls_private_key_configured $true) -or
        $startup.blocker_codes -isnot [System.Array] -or
        $startup.blocker_codes.Count -ne 0
    ) {
        Write-StartupFailure $manifest
        exit 1
    }
    # A positive startup path is intentionally unavailable in this candidate:
    # formal trust material, controlled service identity, and TLS deployment are not approved.
    Write-StartupFailure $manifest
    exit 1
}
catch {
    Write-StartupFailure $null
    exit 1
}
