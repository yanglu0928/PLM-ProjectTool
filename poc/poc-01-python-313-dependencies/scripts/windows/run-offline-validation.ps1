param(
    [Parameter(Mandatory = $true)]
    [string]$WheelhousePath,
    [string]$PythonLauncher = "py",
    [string]$PythonTag = "-3.13",
    [string]$EvidencePlatform = "windows-server-2025",
    [switch]$UseExistingPython
)

$ErrorActionPreference = "Stop"
$pocRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$repoRoot = (Resolve-Path (Join-Path $pocRoot "..\..")).Path
$runtimeRoot = Join-Path $repoRoot ".poc-runtime\poc-01\windows-offline"
$evidenceRoot = Join-Path $pocRoot ("evidence\" + $EvidencePlatform)
$requirements = Join-Path $pocRoot "requirements\all.txt"
$collector = Join-Path $pocRoot "scripts\collect_environment.py"
$verifier = Join-Path $pocRoot "scripts\verify_imports.py"
$resolvedWheelhouse = (Resolve-Path $WheelhousePath).Path

New-Item -ItemType Directory -Force -Path $evidenceRoot | Out-Null
if ($UseExistingPython) {
    $python = (Resolve-Path -LiteralPath $PythonLauncher).Path
} else {
    New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
    $launcherArguments = @()
    if ($PythonTag) {
        $launcherArguments += $PythonTag
    }
    & $PythonLauncher @launcherArguments -m venv $runtimeRoot
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $python = Join-Path $runtimeRoot "Scripts\python.exe"
}
function Invoke-PipCommand {
    param(
        [string[]]$Arguments,
        [string]$LogPath
    )

    $stdoutPath = "$LogPath.stdout"
    $stderrPath = "$LogPath.stderr"
    $process = Start-Process `
        -FilePath $python `
        -ArgumentList $Arguments `
        -Wait `
        -PassThru `
        -NoNewWindow `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath
    @(
        Get-Content -LiteralPath $stdoutPath -ErrorAction SilentlyContinue
        Get-Content -LiteralPath $stderrPath -ErrorAction SilentlyContinue
    ) | Set-Content -LiteralPath $LogPath -Encoding UTF8
    Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    return $process.ExitCode
}

$quotedWheelhouse = '"' + $resolvedWheelhouse + '"'
$quotedRequirements = '"' + $requirements + '"'
$bootstrapExitCode = Invoke-PipCommand `
    -Arguments @("-m", "pip", "install", "--no-index", "--find-links", $quotedWheelhouse, "pip", "setuptools", "wheel") `
    -LogPath (Join-Path $evidenceRoot "offline-bootstrap.txt")
$installExitCode = Invoke-PipCommand `
    -Arguments @("-m", "pip", "install", "--no-index", "--find-links", $quotedWheelhouse, "-r", $quotedRequirements) `
    -LogPath (Join-Path $evidenceRoot "offline-install.txt")
if ($bootstrapExitCode -ne 0) { exit $bootstrapExitCode }
if ($installExitCode -ne 0) { exit $installExitCode }
& $python $collector | Set-Content -Encoding utf8 (Join-Path $evidenceRoot "environment.json")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python $verifier | Tee-Object -FilePath (Join-Path $evidenceRoot "verification.json")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
