$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$allowedRoot = (Resolve-Path -LiteralPath (Join-Path $repoRoot 'artifacts\package-prep\windows11')).Path
$verifier = Join-Path $repoRoot 'tools\verify_windows_python_runtime.ps1'
$testRoot = Join-Path $allowedRoot ('python-runtime-negative-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $testRoot | Out-Null

function Assert-Rejected {
    param([string]$Archive, [string]$ExpectedError)
    $rejected = $false
    try { & $verifier -Archive $Archive | Out-Null }
    catch {
        if (-not $_.Exception.Message.Contains($ExpectedError, [StringComparison]::Ordinal)) {
            throw "Unexpected runtime rejection: $($_.Exception.Message)"
        }
        $rejected = $true
    }
    if (-not $rejected) { throw 'Unsafe Python runtime archive accepted' }
}

try {
    $wrongName = Join-Path $testRoot 'python-3.13.15-embeddable-amd64.zip'
    [IO.File]::WriteAllBytes($wrongName, [byte[]](0x50, 0x4b, 0x03, 0x04))
    Assert-Rejected -Archive $wrongName -ExpectedError 'Only the staged official'
    $badHash = Join-Path $testRoot 'python-3.13.15-embed-amd64.zip'
    [IO.File]::WriteAllBytes($badHash, [byte[]](0x50, 0x4b, 0x03, 0x04))
    Assert-Rejected -Archive $badHash -ExpectedError 'SHA-256 mismatch'
    Write-Output '2/2 incorrect runtime artifacts rejected before extraction'
} finally {
    $resolved = (Resolve-Path -LiteralPath $testRoot).Path
    if (-not $resolved.StartsWith($allowedRoot + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase) -or
        (Split-Path -Leaf $resolved) -notlike 'python-runtime-negative-*') {
        throw 'Refusing cleanup outside verified test directory'
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
