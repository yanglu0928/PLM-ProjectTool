param(
    [Parameter(Mandatory = $true)] [string] $GraphPath,
    [Parameter(Mandatory = $true)] [string] $OfficialPayloadDir,
    [Parameter(Mandatory = $true)] [string] $DebianRuntimeArchivePath,
    [Parameter(Mandatory = $true)] [string] $DebianRuntimeExtractedDir,
    [Parameter(Mandatory = $true)] [string] $DebianBaseArchivePath,
    [Parameter(Mandatory = $true)] [string] $DebianBaseCopyrightPath,
    [Parameter(Mandatory = $true)] [string] $OutputPath
)

$ErrorActionPreference = 'Stop'
$runtimeExpected = 'c898d96177574a8a7238564a1e799d8ddfed5a3d2ea005510305f9ad466a6f59'
$baseExpected = '8d2c64b886ab4a435a78ddc4cd3b510f149b65fbd6be8472e8f460627562718a'
$runtimeSha = (Get-FileHash -LiteralPath $DebianRuntimeArchivePath -Algorithm SHA256).Hash.ToLowerInvariant()
$baseSha = (Get-FileHash -LiteralPath $DebianBaseArchivePath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($runtimeSha -ne $runtimeExpected -or $baseSha -ne $baseExpected) {
    throw 'Debian archive SHA differs from published Debian package download pages'
}
$graph = Get-Content -LiteralPath $GraphPath -Raw | ConvertFrom-Json
$rows = @()
foreach ($name in @('libgcc_s_seh-1.dll', 'libstdc++-6.dll')) {
    $official = Join-Path $OfficialPayloadDir $name
    $debian = Join-Path $DebianRuntimeExtractedDir "usr/lib/gcc/x86_64-w64-mingw32/14-posix/$name"
    $officialSha = (Get-FileHash -LiteralPath $official -Algorithm SHA256).Hash.ToLowerInvariant()
    $debianSha = (Get-FileHash -LiteralPath $debian -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($officialSha -ne $graph.needed_sha256.$name -or $officialSha -ne $debianSha) {
        throw "Debian runtime binary differs from official Tesseract asset or PE graph: $name"
    }
    $rows += [pscustomobject]@{
        dll = $name
        sha256 = $officialSha
        official_size = (Get-Item -LiteralPath $official).Length
        debian_size = (Get-Item -LiteralPath $debian).Length
        package = 'gcc-mingw-w64-x86-64-posix-runtime'
        version = '14.2.0-19+27+b1'
        archive_sha256 = $runtimeSha
        status = 'EXACT_BINARY_MATCH_DEBIAN_PACKAGE'
    }
}
$copyrightSha = (Get-FileHash -LiteralPath $DebianBaseCopyrightPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($copyrightSha -ne 'f891d7e0c56f503a92c7258d540b3d8215852d8387cbca8f1f07c6f4b6e67da6') {
    throw 'Debian base copyright text differs from audited package content'
}
$result = [ordered]@{
    schema_version = 1
    release_eligible = $false
    exact_match_count = $rows.Count
    debian_runtime_archive_sha256 = $runtimeSha
    debian_base_archive_sha256 = $baseSha
    debian_base_copyright_sha256 = $copyrightSha
    build_host_inference_not_proven = $true
    legal_review_complete = $false
    rows = $rows
}
$outDir = Split-Path -Parent $OutputPath
if ($outDir) { New-Item -ItemType Directory -Force -Path $outDir | Out-Null }
Set-Content -LiteralPath $OutputPath -Value ($result | ConvertTo-Json -Depth 8) -Encoding utf8
[pscustomobject]$result | Select-Object exact_match_count, release_eligible
