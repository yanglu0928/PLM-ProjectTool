$ErrorActionPreference = "Stop"
function Test-StrictJsonBoolean($value, [bool]$expected) {
    return ($null -ne $value -and $value.GetType() -eq [bool] -and $value -eq $expected)
}
try {
    $payloadRoot = $PSScriptRoot
    $packageRoot = Split-Path -Parent $payloadRoot
    $manifestPath = Join-Path $packageRoot "manifest.json"
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        throw "manifest missing"
    }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $startup = $manifest.startup_preflight
    $expectedFields = @(
        "blocker_codes", "database_credential_reference_verified",
        "database_credential_target_reference", "formal_license_trust_verified",
        "formal_startup_ready", "packaged_product_public_key_resource_present",
        "service_identity_acl_verified", "tls_certificate_configured",
        "tls_private_key_configured"
    )
    if ($null -eq $startup -or
        (@($startup.PSObject.Properties.Name | Sort-Object) -join "|") -ne
        ($expectedFields -join "|") -or
        $manifest.kind -ne "WINDOWS_PARENT_PACKAGE_NON_RELEASE_CANDIDATE" -or
        -not (Test-StrictJsonBoolean $manifest.release_eligible $false) -or
        -not (Test-StrictJsonBoolean $manifest.legal_clearance $false) -or
        $startup.database_credential_target_reference -isnot [string] -or
        $startup.database_credential_target_reference -ne "PLMProjectTool/Database" -or
        $startup.blocker_codes -isnot [System.Array]
    ) {
        throw "manifest contract rejected"
    }
    $actualCodes = [System.Collections.Generic.List[string]]::new()
    $boolFields = @(
        @{ Key = "formal_startup_ready"; Code = "FORMAL_STARTUP_NOT_READY"; Expected = $true },
        @{ Key = "packaged_product_public_key_resource_present"; Code = "FORMAL_PRODUCT_PUBLIC_KEY_NOT_PACKAGED"; Expected = $true },
        @{ Key = "formal_license_trust_verified"; Code = "FORMAL_LICENSE_TRUST_NOT_VERIFIED"; Expected = $true },
        @{ Key = "database_credential_reference_verified"; Code = "DATABASE_CREDENTIAL_REFERENCE_NOT_VERIFIED"; Expected = $true },
        @{ Key = "service_identity_acl_verified"; Code = "SERVICE_IDENTITY_ACL_NOT_VERIFIED"; Expected = $true },
        @{ Key = "tls_certificate_configured"; Code = "TLS_CERTIFICATE_CONFIGURATION_NOT_VERIFIED"; Expected = $true },
        @{ Key = "tls_private_key_configured"; Code = "TLS_PRIVATE_KEY_NOT_CONFIGURED"; Expected = $true }
    )
    foreach ($field in $boolFields) {
        $value = $startup.($field.Key)
        if ($null -eq $value -or $value.GetType() -ne [bool]) {
            throw "manifest boolean type rejected"
        }
        if ($value -ne $field.Expected) { $actualCodes.Add($field.Code) }
    }
    if ($startup.blocker_codes.Count -ne @($startup.blocker_codes | Where-Object { $_ -is [string] }).Count) {
        throw "manifest blocker type rejected"
    }
    $declaredCodes = @($startup.blocker_codes | Sort-Object)
    $computedCodes = @($actualCodes | Sort-Object)
    if (($declaredCodes -join "|") -ne ($computedCodes -join "|")) {
        throw "manifest blocker list mismatch"
    }

    # This tool diagnoses a non-release candidate only. It never declares a candidate ready.
    $actualCodes.Add("NON_RELEASE_CANDIDATE")
    $labels = @{
        "FORMAL_STARTUP_NOT_READY" = "The formal startup readiness check is incomplete."
        "FORMAL_PRODUCT_PUBLIC_KEY_NOT_PACKAGED" = "The formal product public key is not packaged."
        "FORMAL_LICENSE_TRUST_NOT_VERIFIED" = "Formal License trust has not been verified."
        "DATABASE_CREDENTIAL_REFERENCE_NOT_VERIFIED" = "The approved database credential reference has not been verified."
        "SERVICE_IDENTITY_ACL_NOT_VERIFIED" = "The service identity and folder permissions have not been verified."
        "TLS_CERTIFICATE_CONFIGURATION_NOT_VERIFIED" = "TLS certificate configuration has not been verified."
        "TLS_PRIVATE_KEY_NOT_CONFIGURED" = "TLS private key configuration has not been verified."
        "NON_RELEASE_CANDIDATE" = "This package is a non-release candidate and cannot be started."
    }
    $report = [ordered]@{
        status = "BLOCKED"
        release_eligible = $false
        legal_clearance = $false
        blocker_codes = @($actualCodes)
        messages = @($actualCodes | ForEach-Object { $labels[$_] })
    }
    Write-Output ($report | ConvertTo-Json -Depth 5 -Compress)
    exit 2
}
catch {
    [Console]::Error.WriteLine("Startup preflight diagnostic rejected; manifest invalid.")
    exit 2
}
