param(
    [Parameter(Mandatory = $true)] [string]$CandidateArchive,
    [Parameter(Mandatory = $true)] [string]$PythonExe
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$allowedRoot = (Resolve-Path -LiteralPath (Join-Path $repoRoot 'artifacts\package-prep\windows11')).Path
$archive = (Resolve-Path -LiteralPath $CandidateArchive).Path
$python = (Resolve-Path -LiteralPath $PythonExe).Path
if (-not $archive.StartsWith($allowedRoot + [IO.Path]::DirectorySeparatorChar,
        [StringComparison]::OrdinalIgnoreCase) -or
    (Split-Path -Leaf $archive) -ne 'NOT-FOR-RELEASE-windows11-candidate.zip') {
    throw 'Only a local NOT-FOR-RELEASE Windows11 candidate archive is accepted'
}
if (-not (Test-Path -LiteralPath $archive -PathType Leaf)) { throw 'Candidate archive missing' }

$identity = & $python -c 'import json,platform,struct,sys; print(json.dumps({"version":sys.version_info[:2],"bits":struct.calcsize("P")*8,"system":platform.system(),"machine":platform.machine()}))'
if ($LASTEXITCODE -ne 0) { throw 'Python identity check failed' }
$runtime = $identity | ConvertFrom-Json
if ($runtime.version[0] -ne 3 -or $runtime.version[1] -ne 13 -or $runtime.bits -ne 64 -or
    $runtime.system -ne 'Windows' -or $runtime.machine -notin @('AMD64', 'x86_64')) {
    throw 'Windows Python 3.13 x64 is required'
}

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [IO.Compression.ZipFile]::OpenRead($archive)
try {
    $seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $files = @()
    $totalBytes = [int64]0
    foreach ($entry in $zip.Entries) {
        $name = $entry.FullName
        if (-not $name -or $name.Contains('\') -or $name.StartsWith('/') -or
            $name.Contains(':') -or ($name.TrimEnd('/').Split('/') | Where-Object { $_ -in @('', '.', '..') } | Select-Object -First 1)) {
            throw 'Candidate ZIP entry path rejected'
        }
        if (-not $seen.Add($name.TrimEnd('/'))) { throw 'Candidate ZIP duplicate entry rejected' }
        $fileKind = (([uint32]$entry.ExternalAttributes -shr 16) -band 0xF000)
        if ($fileKind -eq 0xA000) { throw 'Candidate ZIP symlink rejected' }
        if ($name.EndsWith('/')) { continue }
        if ($name -ne 'manifest.json' -and $name -ne 'payload-sha256sums.txt' -and
            -not $name.StartsWith('payload/', [StringComparison]::Ordinal)) {
            throw 'Candidate ZIP unexpected entry rejected'
        }
        $totalBytes += $entry.Length
        if ($totalBytes -gt 1073741824) { throw 'Candidate ZIP expanded size rejected' }
        $files += $name
    }
    if ($files -notcontains 'manifest.json' -or $files -notcontains 'payload-sha256sums.txt' -or
        @($files | Where-Object { $_.StartsWith('payload/', [StringComparison]::Ordinal) }).Count -lt 3) {
        throw 'Candidate ZIP mandatory entries missing'
    }
} finally {
    $zip.Dispose()
}

$runRoot = Join-Path $allowedRoot ('reinstall-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
$unpacked = Join-Path $runRoot 'unpacked'
New-Item -ItemType Directory -Path $unpacked -Force | Out-Null
[IO.Compression.ZipFile]::ExtractToDirectory($archive, $unpacked)
$manifest = Get-Content -LiteralPath (Join-Path $unpacked 'manifest.json') -Raw | ConvertFrom-Json
if ($manifest.kind -ne 'WINDOWS11_DEVELOPMENT_CANDIDATE_PAYLOAD' -or
    $manifest.release_eligible -ne $false -or $manifest.payload_sha256_manifest -ne 'payload-sha256sums.txt') {
    throw 'Candidate manifest type or release gate rejected'
}
$payload = Join-Path $unpacked 'payload'
$lines = @(Get-Content -LiteralPath (Join-Path $unpacked 'payload-sha256sums.txt'))
$actual = @(Get-ChildItem -LiteralPath $payload -Recurse -File)
if ($lines.Count -ne $actual.Count -or $lines.Count -ne $manifest.payload_file_count) {
    throw 'Candidate payload file count mismatch'
}
$listed = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
foreach ($line in $lines) {
    $match = [regex]::Match($line, '^([0-9a-f]{64})  ((?:backend/wheelhouse/[A-Za-z0-9_.+-]+\.whl)|(?:frontend/dist/[A-Za-z0-9_.\/-]+)|(?:config/bootstrap\.example\.yaml))$')
    if (-not $match.Success) { throw 'Candidate payload manifest line rejected' }
    $name = $match.Groups[2].Value
    if ($name.Split('/') | Where-Object { $_ -in @('.', '..') }) { throw 'Candidate payload traversal rejected' }
    if (-not $listed.Add($name)) { throw 'Candidate payload duplicate rejected' }
    $path = Join-Path $payload ($name.Replace('/', [IO.Path]::DirectorySeparatorChar))
    $item = Get-Item -LiteralPath $path -ErrorAction Stop
    if ($item.Attributes.HasFlag([IO.FileAttributes]::ReparsePoint)) { throw 'Candidate payload reparse point rejected' }
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $match.Groups[1].Value) {
        throw 'Candidate payload hash mismatch'
    }
}
if ($listed.Count -ne $actual.Count -or @($actual | Where-Object {
    -not $listed.Contains($_.FullName.Substring($payload.Length + 1).Replace('\', '/'))
}).Count -ne 0) {
    throw 'Candidate payload contains unlisted file'
}
$wheelhouse = Join-Path $payload 'backend\wheelhouse'
$ownWheels = @(Get-ChildItem -LiteralPath $wheelhouse -File -Filter 'plm_project_tool_backend-*.whl')
if ($ownWheels.Count -ne 1 -or $ownWheels[0].Name -ne $manifest.backend_wheel -or
    -not (Test-Path -LiteralPath (Join-Path $payload 'frontend\dist\index.html') -PathType Leaf)) {
    throw 'Candidate product files mismatch'
}

$venv = Join-Path $runRoot 'verify-venv'
& $python -m venv $venv
if ($LASTEXITCODE -ne 0) { throw 'Candidate clean venv creation failed' }
$venvPython = Join-Path $venv 'Scripts\python.exe'
& $venvPython -m pip install --disable-pip-version-check --no-index --find-links $wheelhouse $ownWheels[0].FullName
if ($LASTEXITCODE -ne 0) { throw 'Candidate no-index installation failed' }
& $venvPython -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Candidate dependency check failed' }
& $venvPython -c 'import alembic,fastapi,fitz,openpyxl,paddle,paddleocr,paddlex,psycopg,sqlalchemy,uvicorn; import plm_assistant; from importlib import metadata; assert metadata.version("plm-project-tool-backend")==plm_assistant.__version__'
if ($LASTEXITCODE -ne 0) { throw 'Candidate import smoke failed' }

[ordered]@{
    status = 'WINDOWS11_CANDIDATE_REINSTALL_PASS'
    release_eligible = $false
    archive_sha256 = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    payload_file_count = $listed.Count
    wheel_count = @(Get-ChildItem -LiteralPath $wheelhouse -File).Count
    verification = 'ZIP entry/hash checks, fresh Python3.13 venv, --no-index install, pip check, imports'
    run_root = $runRoot
} | ConvertTo-Json -Depth 4
