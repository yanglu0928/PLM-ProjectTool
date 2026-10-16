param(
    [Parameter(Mandatory = $true)] [string]$RuntimeArchive,
    [Parameter(Mandatory = $true)] [string]$BuilderPython
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$allowedRoot = (Resolve-Path -LiteralPath (Join-Path $repoRoot 'artifacts\package-prep\windows11')).Path
$builder = Join-Path $repoRoot 'tools\build_windows_embedded_backend.ps1'
$testRoot = Join-Path $allowedRoot ('embedded-backend-negative-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $testRoot | Out-Null

function Assert-Rejected {
    param([string]$Archive, [string]$BackendRoot, [string]$Expected)
    $rejected = $false
    try {
        & $builder -RuntimeArchive $Archive -BackendRunRoot $BackendRoot -BuilderPython $BuilderPython | Out-Null
    } catch {
        if (-not $_.Exception.Message.Contains($Expected, [StringComparison]::Ordinal)) {
            throw "Unexpected embedded build rejection: $($_.Exception.Message)"
        }
        $rejected = $true
    }
    if (-not $rejected) { throw 'Unsafe embedded build input accepted' }
}

try {
    $badRuntime = Join-Path $testRoot 'python-3.13.15-embed-amd64.zip'
    [IO.File]::WriteAllBytes($badRuntime, [byte[]](0x50, 0x4b, 0x03, 0x04))
    Assert-Rejected -Archive $badRuntime -BackendRoot $testRoot -Expected 'runtime SHA-256 mismatch'
    ([ordered]@{ status = 'WINDOWS11_BACKEND_WHEELHOUSE_INDEX_OFFLINE_PASS'; wheel_count = 93 } |
        ConvertTo-Json) | Set-Content -LiteralPath (Join-Path $testRoot 'summary.json') -Encoding utf8
    New-Item -ItemType Directory -Path (Join-Path $testRoot 'wheelhouse') | Out-Null
    Set-Content -LiteralPath (Join-Path $testRoot 'sha256sums.txt') -Value ''
    Assert-Rejected -Archive $RuntimeArchive -BackendRoot $testRoot -Expected 'wheelhouse count mismatch'
    Write-Output '2/2 invalid embedded build inputs rejected before installation'
} finally {
    $resolved = (Resolve-Path -LiteralPath $testRoot).Path
    if (-not $resolved.StartsWith($allowedRoot + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase) -or
        (Split-Path -Leaf $resolved) -notlike 'embedded-backend-negative-*') {
        throw 'Refusing cleanup outside verified test directory'
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
