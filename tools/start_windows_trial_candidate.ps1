$ErrorActionPreference = "Stop"
$ErrorActionPreference = "Stop"
try {
    $payloadRoot = Split-Path -Parent $PSScriptRoot
    $manifestPath = Join-Path $payloadRoot "manifest.json"
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        throw "manifest missing"
    }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($manifest.kind -ne "WINDOWS_PARENT_PACKAGE_NON_RELEASE_CANDIDATE"
        -or $manifest.release_eligible -ne $false
        -or $manifest.legal_clearance -ne $false
        -or $manifest.startup_preflight.formal_startup_ready -ne $true
        -or $manifest.startup_preflight.packaged_product_public_key_resource_present -ne $true
        -or @($manifest.startup_preflight.blocker_codes).Count -ne 0) {
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
