param(
    [Parameter(Mandatory = $true)][string]$MsYsRoot,
    [Parameter(Mandatory = $true)][string]$SourcePackageArchive,
    [Parameter(Mandatory = $true)][string]$ExtractedSourceRoot,
    [Parameter(Mandatory = $true)][string]$OriginalDll,
    [Parameter(Mandatory = $true)][string]$OutputRoot
)

$ErrorActionPreference = 'Stop'
$expected = @{
    sourcePackage = '11f3bdc23a154a5cea2f8fffeab3e2a118bd773d2769e1dcea926ff02f2cf3e2'
    upstreamTar = '672bd7d10aee4606171afb864f3570b83340f6a33e2c186dc0512f7145ffdf6a'
    pkgbuild = '2eecac8b6120c97e3b2754098f57c9bd026dcc121f67a9e2f9bf7e1a689e9819'
    patch = '493742947c8667655b6b89f2d7d27e92e1438a490ed86f50811112394b432a12'
}
function Digest([string]$path) {
    return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
}
$msys = (Resolve-Path -LiteralPath $MsYsRoot).Path
$sourcePackage = (Resolve-Path -LiteralPath $SourcePackageArchive).Path
$source = (Resolve-Path -LiteralPath $ExtractedSourceRoot).Path
$old = (Resolve-Path -LiteralPath $OriginalDll).Path
$target = [IO.Path]::GetFullPath($OutputRoot)
if (Test-Path -LiteralPath $target) { throw 'Output root exists; no overwrite' }
if ($target -notmatch '^[A-Z]:\\[\x20-\x7E]+$' -or $target.Contains('"')) {
    throw 'PoC build root must be an ASCII absolute Windows path'
}
$srcArchive = Join-Path $source 'tiff-4.7.2.tar.gz'
$pkgbuild = Join-Path $source 'PKGBUILD'
$patch = Join-Path $source '0002-libtiff-install-headers.patch'
foreach ($check in @(
    @($sourcePackage, $expected.sourcePackage),
    @($srcArchive, $expected.upstreamTar),
    @($pkgbuild, $expected.pkgbuild),
    @($patch, $expected.patch)
)) {
    if ((Digest $check[0]) -ne $check[1]) { throw "Fixed source input differs: $($check[0])" }
}
$recipe = Get-Content -LiteralPath $pkgbuild -Raw
if (([regex]::Matches($recipe, '--enable-jbig')).Count -ne 2) {
    throw 'Historical package recipe no longer has two JBIG-enabled builds'
}
$paths = @(tar -tf $srcArchive)
if ($LASTEXITCODE -ne 0 -or @($paths | Where-Object {
    $_ -notlike 'tiff-4.7.2/*' -and $_ -ne 'tiff-4.7.2/' -or $_ -match '(^|/)\.\.(/|$)' -or $_ -match '^/'
}).Count -ne 0) { throw 'Upstream tar entries rejected' }
$bash = Join-Path $msys 'usr\bin\bash.exe'
$objdump = Join-Path $msys 'mingw64\bin\objdump.exe'
if (-not (Test-Path -LiteralPath $bash -PathType Leaf) -or
    -not (Test-Path -LiteralPath $objdump -PathType Leaf)) { throw 'Build toolchain missing' }
New-Item -ItemType Directory -Path (Join-Path $target 'src'), (Join-Path $target 'build') | Out-Null
Copy-Item -LiteralPath $srcArchive -Destination (Join-Path $target 'src\tiff-4.7.2.tar.gz')
tar -xf (Join-Path $target 'src\tiff-4.7.2.tar.gz') -C (Join-Path $target 'src')
if ($LASTEXITCODE -ne 0) { throw 'Upstream tar extraction failed' }
$priorSystem = $env:MSYSTEM
$priorRoot = $env:PLM_LIBTIFF_BUILD_ROOT
try {
    $env:MSYSTEM = 'MINGW64'
    $env:PLM_LIBTIFF_BUILD_ROOT = $target
    $packages = @(& $bash -lc 'pacman -Q mingw-w64-x86_64-gcc mingw-w64-x86_64-libtiff')
    if ($LASTEXITCODE -ne 0) { throw 'Toolchain package inventory failed' }
    & $bash -lc 'cd "$(cygpath -u "$PLM_LIBTIFF_BUILD_ROOT")/build" && CFLAGS="-O2 -fno-strict-aliasing" CXXFLAGS="-O2 -fno-strict-aliasing" ../src/tiff-4.7.2/configure --prefix=/mingw64 --build=$MINGW_CHOST --host=$MINGW_CHOST --target=$MINGW_CHOST --disable-static --enable-shared --enable-cxx --disable-jbig --enable-lerc --enable-libdeflate --enable-webp && make -j4 && make check -j4'
    if ($LASTEXITCODE -ne 0) { throw 'No-JBIG build or tests failed' }
} finally {
    $env:MSYSTEM = $priorSystem
    $env:PLM_LIBTIFF_BUILD_ROOT = $priorRoot
}
$built = Join-Path $target 'build\libtiff\.libs\libtiff-6.dll'
if (-not (Test-Path -LiteralPath $built -PathType Leaf)) { throw 'Built DLL missing' }
$imports = @(& $objdump -p $built | ForEach-Object {
    if ($_ -match '^\s*DLL Name:\s*(\S+)') { $Matches[1].ToLowerInvariant() }
})
if ($imports -contains 'libjbig-0.dll') { throw 'Built DLL still imports JBIG' }
$exportPattern = '^\s*\[\s*\d+\]\s+\+base\[\s*\d+\]\s+[0-9a-f]+\s+(\S+)'
$oldExports = @(& $objdump -p $old | ForEach-Object { if ($_ -match $exportPattern) { $Matches[1] } })
$newExports = @(& $objdump -p $built | ForEach-Object { if ($_ -match $exportPattern) { $Matches[1] } })
if ($oldExports.Count -eq 0 -or @(Compare-Object $oldExports $newExports).Count -ne 0) {
    throw 'Export name set differs from fixed MSYS2 libtiff'
}
Copy-Item -LiteralPath $built -Destination (Join-Path $target 'libtiff-6.dll')
$testLog = Get-Content -LiteralPath (Join-Path $target 'build\test\test-suite.log') -Raw
if ($testLog -notmatch '# TOTAL:\s*105' -or $testLog -notmatch '# PASS:\s*105' -or
    $testLog -notmatch '# FAIL:\s*0' -or $testLog -notmatch '# ERROR:\s*0') {
    throw 'LibTIFF test-suite summary differs from expected 105/105'
}
$manifest = [ordered]@{
    status = 'NON_RELEASE_SOURCE_BUILD_POC'
    release_eligible = $false
    source_package_sha256 = $expected.sourcePackage
    upstream_tar_sha256 = $expected.upstreamTar
    pkgbuild_sha256 = $expected.pkgbuild
    applied_package_patch = $false
    option_override = '--disable-jbig'
    toolchain_packages = $packages
    output_sha256 = (Digest (Join-Path $target 'libtiff-6.dll'))
    output_imports = @($imports | Sort-Object)
    export_name_count = $newExports.Count
    libtiff_tests = '105/105 PASS'
    limitation = 'No signed/reproducible release package, full runtime or legal clearance'
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $target 'build-manifest.json') -Encoding utf8
Write-Output ($manifest | ConvertTo-Json -Depth 5 -Compress)
