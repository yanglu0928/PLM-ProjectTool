param(
    [string]$OutputPath = "C:\POC-01\evidence\probe.json"
)

$ErrorActionPreference = "Stop"

function Get-ExecutableInfo {
    param([string]$Name)

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $command) {
        return [ordered]@{ available = $false; path = $null; version = $null }
    }

    $version = (& $command.Source --version 2>&1 | Out-String).Trim()
    return [ordered]@{
        available = $true
        path = [IO.Path]::GetFileName($command.Source)
        version = $version
    }
}

$os = Get-CimInstance Win32_OperatingSystem
$computer = Get-CimInstance Win32_ComputerSystem
$processor = Get-CimInstance Win32_Processor | Select-Object -First 1
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
$isAdministrator = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$currentVersion = Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion"
$systemDrive = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$($env:SystemDrive)'"

$tesseractPath = "C:\Program Files\Tesseract-OCR\tesseract.exe"
$ghostscriptPaths = @(Get-ChildItem "C:\Program Files\gs\*\bin\gswin64c.exe" -ErrorAction SilentlyContinue)

$report = [ordered]@{
    operating_system = [ordered]@{
        caption = $os.Caption
        version = $os.Version
        build_number = $os.BuildNumber
        architecture = $os.OSArchitecture
        edition_id = $currentVersion.EditionID
        installation_type = $currentVersion.InstallationType
    }
    hardware = [ordered]@{
        logical_processors = $computer.NumberOfLogicalProcessors
        memory_gb = [math]::Round($computer.TotalPhysicalMemory / 1GB, 2)
        processor = $processor.Name.Trim()
        system_drive_free_gb = [math]::Round($systemDrive.FreeSpace / 1GB, 2)
    }
    execution = [ordered]@{
        is_administrator = $isAdministrator
        powershell_version = $PSVersionTable.PSVersion.ToString()
        culture = [Globalization.CultureInfo]::CurrentCulture.Name
        ui_culture = [Globalization.CultureInfo]::CurrentUICulture.Name
    }
    executables = [ordered]@{
        python = Get-ExecutableInfo "python.exe"
        py_launcher = Get-ExecutableInfo "py.exe"
        tesseract = [ordered]@{
            available = Test-Path -LiteralPath $tesseractPath -PathType Leaf
            path = if (Test-Path -LiteralPath $tesseractPath -PathType Leaf) { "tesseract.exe" } else { $null }
        }
        ghostscript = [ordered]@{
            available = $ghostscriptPaths.Count -gt 0
            path = if ($ghostscriptPaths.Count -gt 0) { "gswin64c.exe" } else { $null }
        }
    }
}

$outputDirectory = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
$report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
