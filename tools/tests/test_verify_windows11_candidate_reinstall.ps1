param([Parameter(Mandatory = $true)] [string]$PythonExe)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$allowedRoot = (Resolve-Path -LiteralPath (Join-Path $repoRoot 'artifacts\package-prep\windows11')).Path
$verifier = Join-Path $repoRoot 'tools\verify_windows11_candidate_reinstall.ps1'
$testRoot = Join-Path $allowedRoot ('verify-negative-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $testRoot | Out-Null
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

function Assert-RejectedZip {
    param([string[]]$Names, [string]$ExpectedError)
    $archive = Join-Path $testRoot 'NOT-FOR-RELEASE-windows11-candidate.zip'
    if (Test-Path -LiteralPath $archive) { Remove-Item -LiteralPath $archive }
    $zip = [IO.Compression.ZipFile]::Open($archive, [IO.Compression.ZipArchiveMode]::Create)
    try {
        foreach ($name in $Names) { [void]$zip.CreateEntry($name) }
    } finally { $zip.Dispose() }
    $rejected = $false
    try { & $verifier -CandidateArchive $archive -PythonExe $PythonExe | Out-Null }
    catch {
        if (-not $_.Exception.Message.Contains($ExpectedError, [StringComparison]::Ordinal)) {
            throw "Candidate ZIP rejected for unexpected reason: $($_.Exception.Message)"
        }
        $rejected = $true
    }
    if (-not $rejected) { throw 'Unsafe candidate ZIP was accepted' }
}

try {
    Assert-RejectedZip -Names @('../escape', 'manifest.json', 'payload-sha256sums.txt') -ExpectedError 'entry path rejected'
    Assert-RejectedZip -Names @('manifest.json', 'MANIFEST.JSON', 'payload-sha256sums.txt') -ExpectedError 'duplicate entry rejected'
    Assert-RejectedZip -Names @('manifest.json', 'payload-sha256sums.txt', 'other.bin') -ExpectedError 'unexpected entry rejected'
    Write-Output '3/3 unsafe ZIP variants rejected before extraction'
} finally {
    $resolved = (Resolve-Path -LiteralPath $testRoot).Path
    if (-not $resolved.StartsWith($allowedRoot + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase) -or
        (Split-Path -Leaf $resolved) -notlike 'verify-negative-*') {
        throw 'Refusing cleanup outside verified test directory'
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
