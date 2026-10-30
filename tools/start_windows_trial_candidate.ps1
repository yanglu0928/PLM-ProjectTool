$ErrorActionPreference = "Stop"
function Test-StrictJsonBoolean($value, [bool]$expected) {
    return ($null -ne $value -and $value.GetType() -eq [bool] -and $value -eq $expected)
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
        [Console]::Error.WriteLine("Packaged production startup blocked; trust prerequisites are not ready.")
        exit 1
    }
    # A positive startup path is intentionally unavailable in this candidate:
    # formal trust material, controlled service identity, and TLS deployment are not approved.
    [Console]::Error.WriteLine("Packaged production startup blocked; trust prerequisites are not ready.")
    exit 1
}
catch {
    [Console]::Error.WriteLine("Packaged production startup blocked; trust prerequisites are not ready.")
    exit 1
}
