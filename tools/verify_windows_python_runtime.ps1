param([Parameter(Mandatory = $true)] [string]$Archive)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$allowedRoot = (Resolve-Path -LiteralPath (Join-Path $repoRoot 'artifacts\package-prep\windows11')).Path
$source = (Resolve-Path -LiteralPath $Archive).Path
$expectedHash = 'd1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf'
if (-not $source.StartsWith($allowedRoot + [IO.Path]::DirectorySeparatorChar,
        [StringComparison]::OrdinalIgnoreCase) -or
    (Split-Path -Leaf $source) -ne 'python-3.13.15-embed-amd64.zip') {
    throw 'Only the staged official Python 3.13.15 AMD64 embed ZIP is accepted'
}
if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedHash) {
    throw 'Official Python runtime SHA-256 mismatch'
}

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [IO.Compression.ZipFile]::OpenRead($source)
try {
    $names = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($entry in $zip.Entries) {
        $name = $entry.FullName
        if (-not $name -or $name.Contains('/') -or $name.Contains('\') -or
            $name -in @('.', '..') -or $name.Contains(':') -or
            -not $names.Add($name)) {
            throw 'Official Python runtime ZIP structure rejected'
        }
    }
    foreach ($mandatory in @('python.exe', 'python313.dll', 'python313.zip', 'python313._pth', 'LICENSE.txt')) {
        if (-not $names.Contains($mandatory)) { throw 'Official Python runtime mandatory file missing' }
    }
} finally { $zip.Dispose() }

$runRoot = Join-Path $allowedRoot ('python-runtime-verified-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Path $runRoot | Out-Null
[IO.Compression.ZipFile]::ExtractToDirectory($source, $runRoot)
$interpreter = Join-Path $runRoot 'python.exe'
$identity = & $interpreter -I -c 'import json,platform,struct,sys; print(json.dumps({"version":sys.version_info[:3],"bits":struct.calcsize("P")*8,"system":platform.system(),"machine":platform.machine(),"executable":sys.executable,"paths":sys.path}))'
if ($LASTEXITCODE -ne 0) { throw 'Embedded Python identity execution failed' }
$runtime = $identity | ConvertFrom-Json
if ($runtime.version[0] -ne 3 -or $runtime.version[1] -ne 13 -or $runtime.version[2] -ne 15 -or
    $runtime.bits -ne 64 -or $runtime.system -ne 'Windows' -or
    $runtime.machine -notin @('AMD64', 'x86_64') -or
    -not [IO.Path]::GetFullPath($runtime.executable).Equals($interpreter, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Embedded Python identity mismatch'
}
if (@($runtime.paths | Where-Object {
    -not [IO.Path]::GetFullPath($_).StartsWith($runRoot + [IO.Path]::DirectorySeparatorChar,
        [StringComparison]::OrdinalIgnoreCase) -and
    -not [IO.Path]::GetFullPath($_).Equals($runRoot, [StringComparison]::OrdinalIgnoreCase)
}).Count -ne 0) {
    throw 'Embedded Python search path escaped private runtime'
}
$license = Get-Item -LiteralPath (Join-Path $runRoot 'LICENSE.txt')
if ($license.Length -lt 1000 -or -not (Select-String -LiteralPath $license.FullName -SimpleMatch 'PYTHON SOFTWARE FOUNDATION LICENSE' -Quiet)) {
    throw 'Embedded Python license notice missing'
}
$systemCrt = Join-Path $env:windir 'System32\ucrtbase.dll'
[ordered]@{
    status = 'WINDOWS11_PYTHON_EMBED_SOURCE_PASS'
    source = 'python.org Python 3.13.15 AMD64 embed ZIP'
    sha256 = $expectedHash
    file_count = $names.Count
    version = '3.13.15'
    license_included = $true
    private_search_path = $true
    system_ucrt_present = [bool](Test-Path -LiteralPath $systemCrt -PathType Leaf)
    release_eligible = $false
    verified_root = $runRoot
} | ConvertTo-Json -Depth 4
