param(
    [Parameter(Mandatory = $true)] [string] $GraphPath,
    [Parameter(Mandatory = $true)] [string] $OfficialPayloadDir,
    [Parameter(Mandatory = $true)] [string[]] $ExtractedPackageDirs,
    [Parameter(Mandatory = $true)] [string] $OutputPath
)

$ErrorActionPreference = 'Stop'
$graph = Get-Content -LiteralPath $GraphPath -Raw | ConvertFrom-Json
$rows = @()
$candidates = @()

foreach ($dir in $ExtractedPackageDirs) {
    $root = (Resolve-Path -LiteralPath $dir).Path
    $infoPath = Join-Path $root '.PKGINFO'
    if (-not (Test-Path -LiteralPath $infoPath -PathType Leaf)) {
        throw "Missing package metadata: $infoPath"
    }
    $info = @{}
    foreach ($line in Get-Content -LiteralPath $infoPath) {
        if ($line -match '^([^#= ]+) = (.+)$' -and -not $info.ContainsKey($Matches[1])) {
            $info[$Matches[1]] = $Matches[2]
        }
    }
    foreach ($key in 'pkgname', 'pkgver', 'license') {
        if (-not $info.ContainsKey($key)) { throw "Missing $key in $infoPath" }
    }
    $licenses = @(Get-ChildItem -LiteralPath (Join-Path $root 'mingw64/share/licenses') -File -Recurse -ErrorAction SilentlyContinue)
    $candidates += [pscustomobject]@{
        root = $root
        pkgname = $info.pkgname
        pkgver = $info.pkgver
        declared_license = $info.license
        license_files = @($licenses | ForEach-Object {
            [pscustomobject]@{
                relative_path = [System.IO.Path]::GetRelativePath($root, $_.FullName).Replace('\', '/')
                sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
            }
        })
    }
}

foreach ($name in @($graph.needed_local_files | Where-Object { $_ -like '*.dll' } | Sort-Object)) {
    $official = Join-Path $OfficialPayloadDir $name
    if (-not (Test-Path -LiteralPath $official -PathType Leaf)) { throw "Missing official DLL: $official" }
    $sha = (Get-FileHash -LiteralPath $official -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($sha -ne $graph.needed_sha256.$name) { throw "Official payload differs from frozen PE graph: $name" }
    $matches = @()
    $rejected = @()
    foreach ($pkg in $candidates) {
        $candidatePath = Join-Path $pkg.root "mingw64/bin/$name"
        if (-not (Test-Path -LiteralPath $candidatePath -PathType Leaf)) { continue }
        $candidateSha = (Get-FileHash -LiteralPath $candidatePath -Algorithm SHA256).Hash.ToLowerInvariant()
        $entry = [pscustomobject]@{
            pkgname = $pkg.pkgname
            pkgver = $pkg.pkgver
            binary_sha256 = $candidateSha
            declared_license = $pkg.declared_license
            license_files = $pkg.license_files
        }
        if ($candidateSha -eq $sha) { $matches += $entry } else { $rejected += $entry }
    }
    $version = (Get-Item -LiteralPath $official).VersionInfo
    $rows += [pscustomobject]@{
        dll = $name
        official_sha256 = $sha
        file_version_resource = $version.FileVersion
        exact_package_matches = @($matches)
        rejected_package_candidates = @($rejected)
        status = if ($matches.Count -gt 0) { 'EXACT_BINARY_MATCH_LICENSE_TEXT_LOCATED' } else { 'EXACT_PACKAGE_AND_LICENSE_UNRESOLVED' }
    }
}

$result = [ordered]@{
    schema_version = 1
    scope = 'Tesseract 5.5.3 Windows CLI static PE graph DLLs only'
    release_eligible = $false
    static_graph_is_not_dynamic_dependency_proof = $true
    dll_count = $rows.Count
    exact_match_count = @($rows | Where-Object { $_.exact_package_matches.Count -gt 0 }).Count
    rows = $rows
}
$json = $result | ConvertTo-Json -Depth 10
$outDir = Split-Path -Parent $OutputPath
if ($outDir) { New-Item -ItemType Directory -Force -Path $outDir | Out-Null }
Set-Content -LiteralPath $OutputPath -Value $json -Encoding utf8
[pscustomobject]$result | Select-Object dll_count, exact_match_count, release_eligible
