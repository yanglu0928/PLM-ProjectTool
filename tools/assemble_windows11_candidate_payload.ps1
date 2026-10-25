param(
    [Parameter(Mandatory = $true)] [string]$BackendRunRoot,
    [Parameter(Mandatory = $true)] [string]$FrontendRunRoot
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$allowedRoot = (Resolve-Path -LiteralPath (Join-Path $repoRoot 'artifacts\package-prep\windows11')).Path
$backendRoot = (Resolve-Path -LiteralPath $BackendRunRoot).Path
$frontendRoot = (Resolve-Path -LiteralPath $FrontendRunRoot).Path
foreach ($sourceRoot in @($backendRoot, $frontendRoot)) {
    if (-not $sourceRoot.StartsWith($allowedRoot + [IO.Path]::DirectorySeparatorChar,
                                    [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Candidate source must be a prior Windows11 package-prep run'
    }
}
$backendWheels = Join-Path $backendRoot 'wheelhouse'
$frontendDist = Join-Path $frontendRoot 'offline-source\apps\frontend\dist'
$backendManifest = Join-Path $backendRoot 'sha256sums.txt'
$frontendManifest = Join-Path $frontendRoot 'dist-sha256sums.txt'
$frontendSummary = Get-Content -LiteralPath (Join-Path $frontendRoot 'summary.json') -Raw | ConvertFrom-Json
if ($frontendSummary.status -ne 'WINDOWS11_FRONTEND_PNPM_OFFLINE_PASS') {
    throw 'Frontend source was not verified offline'
}

function Assert-Manifest {
    param([string]$ManifestPath, [string]$ContentRoot, [string]$Pattern)
    $lines = @(Get-Content -LiteralPath $ManifestPath)
    $actual = @(Get-ChildItem -LiteralPath $ContentRoot -Recurse -File)
    if ($lines.Count -eq 0 -or $lines.Count -ne $actual.Count) {
        throw 'Candidate source manifest count mismatch'
    }
    $names = @()
    foreach ($line in $lines) {
        $matched = [regex]::Match($line, $Pattern)
        if (-not $matched.Success) { throw 'Candidate source manifest entry rejected' }
        $name = $matched.Groups[2].Value
        if ($name.Split('/') | Where-Object { $_ -eq '.' -or $_ -eq '..' }) {
            throw 'Candidate source traversal rejected'
        }
        $target = Join-Path $ContentRoot ($name.Replace('/', [IO.Path]::DirectorySeparatorChar))
        $item = Get-Item -LiteralPath $target -ErrorAction Stop
        if ($item.Attributes.HasFlag([IO.FileAttributes]::ReparsePoint)) {
            throw 'Candidate source reparse point rejected'
        }
        $digest = (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($digest -ne $matched.Groups[1].Value) {
            throw 'Candidate source hash mismatch'
        }
        $names += $name
    }
    if (@($names | Sort-Object -Unique).Count -ne $lines.Count) {
        throw 'Candidate source duplicate rejected'
    }
    return $names
}

$wheelNames = @(Assert-Manifest -ManifestPath $backendManifest -ContentRoot $backendWheels `
    -Pattern '^([0-9a-f]{64})  ([A-Za-z0-9_.+-]+\.whl)$')
$distNames = @(Assert-Manifest -ManifestPath $frontendManifest -ContentRoot $frontendDist `
    -Pattern '^([0-9a-f]{64})  ([A-Za-z0-9_.\/-]+)$')
$ownWheels = @($wheelNames | Where-Object { $_ -match '^plm_project_tool_backend-0\.1\.0\.dev0-.*\.whl$' })
if ($ownWheels.Count -ne 1 -or $wheelNames.Count -lt 2 -or
    $frontendSummary.dist_file_count -ne $distNames.Count) {
    throw 'Candidate product wheel or frontend count mismatch'
}
$frontendPackage = Get-Content -LiteralPath (Join-Path $frontendRoot 'offline-source\apps\frontend\package.json') -Raw | ConvertFrom-Json
if ($frontendPackage.version -ne '0.1.0-dev.0') {
    throw 'Candidate frontend version mismatch'
}
$configSource = Join-Path $repoRoot 'apps\backend\config\bootstrap.example.yaml'
if (-not (Test-Path -LiteralPath $configSource -PathType Leaf)) {
    throw 'Non-secret bootstrap example missing'
}

$runName = 'candidate-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 8)
$runRoot = Join-Path $allowedRoot $runName
$payload = Join-Path $runRoot 'payload'
$destWheels = Join-Path $payload 'backend\wheelhouse'
$destDist = Join-Path $payload 'frontend\dist'
$destConfig = Join-Path $payload 'config'
foreach ($directory in @($destWheels, $destDist, $destConfig)) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}
foreach ($name in $wheelNames) {
    Copy-Item -LiteralPath (Join-Path $backendWheels $name) -Destination (Join-Path $destWheels $name)
}
foreach ($name in $distNames) {
    $destination = Join-Path $destDist ($name.Replace('/', [IO.Path]::DirectorySeparatorChar))
    New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $frontendDist ($name.Replace('/', [IO.Path]::DirectorySeparatorChar))) -Destination $destination
}
Copy-Item -LiteralPath $configSource -Destination (Join-Path $destConfig 'bootstrap.example.yaml')

$copied = @(Get-ChildItem -LiteralPath $payload -Recurse -File | Sort-Object FullName)
if ($copied.Count -ne $wheelNames.Count + $distNames.Count + 1) {
    throw 'Candidate payload file count mismatch'
}
$hashLines = @($copied | ForEach-Object {
    $digest = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $relative = $_.FullName.Substring($payload.Length + 1).Replace('\', '/')
    "$digest  $relative"
})
$hashPath = Join-Path $runRoot 'payload-sha256sums.txt'
$hashLines | Set-Content -LiteralPath $hashPath -Encoding ascii
$manifest = [ordered]@{
    kind = 'WINDOWS11_DEVELOPMENT_CANDIDATE_PAYLOAD'
    release_eligible = $false
    created_utc = (Get-Date).ToUniversalTime().ToString('o')
    backend_wheel = $ownWheels[0]
    frontend_version = $frontendPackage.version
    frontend_source_commit = $frontendSummary.source_commit
    backend_source_manifest_sha256 = (Get-FileHash -LiteralPath $backendManifest -Algorithm SHA256).Hash.ToLowerInvariant()
    frontend_source_manifest_sha256 = (Get-FileHash -LiteralPath $frontendManifest -Algorithm SHA256).Hash.ToLowerInvariant()
    payload_file_count = $copied.Count
    payload_sha256_manifest = 'payload-sha256sums.txt'
    missing_release_components = @(
        'Python 3.13 runtime and installer', 'PostgreSQL 18 and pgvector',
        'OCR system components and vetted model files',
        'Formal License public key and customer license',
        'HTTPS static host and service-account provisioning',
        'Plugin package, installation and upgrade tools',
        'Physical air-gap and Windows Server 2025/Debian 13 acceptance',
        'Gate 3 through Gate 7 evidence and UAT'
    )
}
$manifestPath = Join-Path $runRoot 'manifest.json'
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding utf8
$archive = Join-Path $runRoot 'NOT-FOR-RELEASE-windows11-candidate.zip'
Compress-Archive -LiteralPath $payload, $hashPath, $manifestPath -DestinationPath $archive -CompressionLevel Optimal
$archiveHash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Output ($manifest | ConvertTo-Json -Compress -Depth 5)
Write-Output "Archive SHA-256: $archiveHash"
Write-Output "Artifacts: $runRoot"
