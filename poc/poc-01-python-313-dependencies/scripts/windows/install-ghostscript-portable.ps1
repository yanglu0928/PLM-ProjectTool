param(
    [string]$Version = "10.08.0"
)

$ErrorActionPreference = "Stop"
$pocRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$repoRoot = (Resolve-Path (Join-Path $pocRoot "..\..")).Path

if ($Version -ne "10.08.0") {
    throw "Unsupported Ghostscript version: $Version"
}

$releaseTag = "gs10080"
$installerName = "gs10080w64.exe"
$installerHash = "52a91b8bf09298788d7a57b9206127026c23eacd75405f0a131e26dc381dce50"
$installerUri = "https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/$releaseTag/$installerName"
$sevenZipUri = "https://www.7-zip.org/a/7z2603-x64.msi"
$sevenZipHash = "c0680064d698a62dd4a5a47f403db356a6531a5473e4c4b1d090ea2590513926"

$downloadRoot = Join-Path $repoRoot "artifacts\poc-01\windows\installers"
$installRoot = Join-Path $repoRoot "artifacts\poc-01\windows\ghostscript-$Version-portable"
$toolRoot = Join-Path $repoRoot "artifacts\tools\7zip"
$installer = Join-Path $downloadRoot $installerName
$sevenZipMsi = Join-Path $toolRoot "7z2603-x64.msi"
$sevenZipAdminRoot = Join-Path $toolRoot "app"
$sevenZip = Join-Path $sevenZipAdminRoot "Files\7-Zip\7z.exe"
$ghostscript = Join-Path $installRoot "bin\gswin64c.exe"

New-Item -ItemType Directory -Force -Path $downloadRoot, $toolRoot, $installRoot | Out-Null

if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) {
    Invoke-WebRequest -Uri $installerUri -OutFile $installer
}
if ((Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLower() -ne $installerHash) {
    throw "Ghostscript installer SHA-256 mismatch"
}

$sevenZipCommand = Get-Command 7z.exe -ErrorAction SilentlyContinue
if ($sevenZipCommand) {
    $sevenZip = $sevenZipCommand.Source
} elseif (-not (Test-Path -LiteralPath $sevenZip -PathType Leaf)) {
    if (-not (Test-Path -LiteralPath $sevenZipMsi -PathType Leaf)) {
        Invoke-WebRequest -Uri $sevenZipUri -OutFile $sevenZipMsi
    }
    if ((Get-FileHash -LiteralPath $sevenZipMsi -Algorithm SHA256).Hash.ToLower() -ne $sevenZipHash) {
        throw "7-Zip MSI SHA-256 mismatch"
    }
    New-Item -ItemType Directory -Force -Path $sevenZipAdminRoot | Out-Null
    $arguments = @('/a', "`"$sevenZipMsi`"", '/qn', "TARGETDIR=`"$sevenZipAdminRoot`"")
    $process = Start-Process -FilePath msiexec.exe -ArgumentList $arguments -Wait -PassThru -WindowStyle Hidden
    if ($process.ExitCode -ne 0) {
        throw "7-Zip administrative extraction failed with exit code $($process.ExitCode)"
    }
}

& $sevenZip x $installer "-o$installRoot" -y | Out-Null
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $ghostscript -PathType Leaf)) {
    throw "Ghostscript portable extraction failed"
}

$installedVersion = (& $ghostscript --version).Trim()
if ($installedVersion -ne $Version) {
    throw "Unexpected Ghostscript version: $installedVersion"
}

[ordered]@{
    version = $installedVersion
    executable = $ghostscript
    installer_sha256 = $installerHash
    install_mode = "project-local-portable"
} | ConvertTo-Json
