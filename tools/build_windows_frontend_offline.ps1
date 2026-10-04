$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$nodeVersion = (& node --version).Trim()
$pnpmVersion = (& pnpm --version).Trim()
if ($LASTEXITCODE -ne 0 -or $nodeVersion -notmatch '^v24\.' -or
    $pnpmVersion -ne '11.19.0') {
    throw 'Node 24 and pnpm 11.19.0 are required'
}
$dirtyFrontend = @(& git -C $repoRoot status --porcelain -- apps/frontend)
if ($LASTEXITCODE -ne 0 -or $dirtyFrontend.Count -ne 0) {
    throw 'Frontend source must be clean before archiving HEAD'
}
$commit = (& git -C $repoRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Git source commit unavailable' }

$runName = 'frontend-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 8)
$runRoot = Join-Path $repoRoot ('artifacts\package-prep\windows11\' + $runName)
$archive = Join-Path $runRoot 'frontend-source.zip'
$onlineSource = Join-Path $runRoot 'online-source'
$offlineSource = Join-Path $runRoot 'offline-source'
$store = Join-Path $runRoot 'pnpm-store'
New-Item -ItemType Directory -Path $runRoot | Out-Null
& git -C $repoRoot archive --format=zip --output=$archive HEAD apps/frontend
if ($LASTEXITCODE -ne 0) { throw 'Frontend Git archive failed' }
Expand-Archive -LiteralPath $archive -DestinationPath $onlineSource
Expand-Archive -LiteralPath $archive -DestinationPath $offlineSource
$onlineFrontend = Join-Path $onlineSource 'apps\frontend'
$offlineFrontend = Join-Path $offlineSource 'apps\frontend'
$lockHash = (Get-FileHash -LiteralPath (Join-Path $offlineFrontend 'pnpm-lock.yaml') -Algorithm SHA256).Hash.ToLowerInvariant()

& pnpm -C $onlineFrontend install --frozen-lockfile --store-dir $store
if ($LASTEXITCODE -ne 0) { throw 'Online frozen-lockfile store preparation failed' }
& pnpm -C $offlineFrontend install --offline --frozen-lockfile --store-dir $store
if ($LASTEXITCODE -ne 0) { throw 'Fresh-source offline frontend installation failed' }
$lockHashAfter = (Get-FileHash -LiteralPath (Join-Path $offlineFrontend 'pnpm-lock.yaml') -Algorithm SHA256).Hash.ToLowerInvariant()
if ($lockHashAfter -ne $lockHash) { throw 'Frontend lockfile changed' }
& pnpm -C $offlineFrontend test
if ($LASTEXITCODE -ne 0) { throw 'Offline-installed frontend tests failed' }
& pnpm -C $offlineFrontend build
if ($LASTEXITCODE -ne 0) { throw 'Offline-installed frontend typecheck/build failed' }

$dist = Join-Path $offlineFrontend 'dist'
$files = @(Get-ChildItem -LiteralPath $dist -Recurse -File | Sort-Object FullName)
if ($files.Count -eq 0) { throw 'Frontend dist is empty' }
$hashes = @($files | ForEach-Object {
    $digest = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $relative = $_.FullName.Substring($dist.Length + 1).Replace('\', '/')
    "$digest  $relative"
})
$hashes | Set-Content -LiteralPath (Join-Path $runRoot 'dist-sha256sums.txt') -Encoding ascii
$summary = [ordered]@{
    status = 'WINDOWS11_FRONTEND_PNPM_OFFLINE_PASS'
    created_utc = (Get-Date).ToUniversalTime().ToString('o')
    source_commit = $commit
    node = $nodeVersion
    pnpm = $pnpmVersion
    lock_sha256 = $lockHash
    dist_file_count = $files.Count
    dist_bytes = [int64](($files | Measure-Object Length -Sum).Sum)
    dist_manifest = 'dist-sha256sums.txt'
    verification = 'fresh Git archive, independent store, --offline frozen install, tests, typecheck, build'
    limits = 'Not physical air-gap, Server2025, Debian13, deployment or Release Gate validation'
}
$summary | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $runRoot 'summary.json') -Encoding utf8
Write-Output ($summary | ConvertTo-Json -Compress)
Write-Output "Artifacts: $runRoot"
