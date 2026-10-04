param(
    [Parameter(Mandatory = $true)]
    [string]$BootstrapperPath,
    [string]$InstallPath = "D:\POC-02\BuildTools",
    [string]$OutputPath = "D:\POC-02\build-tools-install.json"
)

$ErrorActionPreference = "Stop"
$bootstrapper = (Resolve-Path -LiteralPath $BootstrapperPath).Path
$expectedSha256 = "37bb0fb429d163ecebd272a865d11a37b906d152bef960da2ddb29c2e2fd6eeb"
$actualSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $bootstrapper).Hash.ToLowerInvariant()
if ($actualSha256 -ne $expectedSha256) {
    throw "Visual Studio Build Tools bootstrapper SHA-256 mismatch"
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
$isAdministrator = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdministrator) {
    throw "Administrator token required; launch this script from an elevated PowerShell"
}

$arguments = @(
    "--quiet",
    "--wait",
    "--norestart",
    "--nocache",
    "--installPath", ('"' + $InstallPath + '"'),
    "--add", "Microsoft.VisualStudio.Workload.VCTools",
    "--includeRecommended"
)
$process = Start-Process -FilePath $bootstrapper -ArgumentList $arguments -Wait -PassThru -WindowStyle Hidden
if ($process.ExitCode -notin @(0, 3010)) {
    throw "Visual Studio Build Tools installer failed with exit code $($process.ExitCode)"
}

$vsDevCmd = Join-Path $InstallPath "Common7\Tools\VsDevCmd.bat"
if (-not (Test-Path -LiteralPath $vsDevCmd -PathType Leaf)) {
    throw "Visual Studio developer command script was not found after installation"
}

$result = [ordered]@{
    status = "PASS"
    installer_version = "17.14.41"
    workload = "Microsoft.VisualStudio.Workload.VCTools"
    install_path = $InstallPath
    restart_required = $process.ExitCode -eq 3010
    completed_at_utc = [DateTime]::UtcNow.ToString("o")
}
$json = $result | ConvertTo-Json
$json | Set-Content -LiteralPath $OutputPath -Encoding UTF8
$json
