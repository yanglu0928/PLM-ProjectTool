param(
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"

function Test-HeadRequest {
    param([string]$Url)

    try {
        $response = Invoke-WebRequest -Uri $Url -Method Head -MaximumRedirection 5 -UseBasicParsing
        return [ordered]@{
            available = $response.StatusCode -eq 200
            status_code = [int]$response.StatusCode
            content_length = [long]($response.Headers."Content-Length" | Select-Object -First 1)
            content_type = [string]($response.Headers."Content-Type" | Select-Object -First 1)
            url = $Url
        }
    } catch {
        return [ordered]@{
            available = $false
            status_code = $null
            content_length = $null
            content_type = $null
            url = $Url
            error = $_.Exception.Message
        }
    }
}

function Get-CommandStatus {
    param([string]$Name)

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    return [ordered]@{
        available = $null -ne $command
        executable_name = if ($command) { [IO.Path]::GetFileName($command.Source) } else { $null }
    }
}

function Test-GitTag {
    param(
        [string]$Repository,
        [string]$Tag,
        [string]$ExpectedCommit
    )

    if (-not (Get-Command "git.exe" -ErrorAction SilentlyContinue)) {
        return [ordered]@{
            available = $false
            tag = $Tag
            expected_commit = $ExpectedCommit
            observed_commit = $null
        }
    }

    $savedErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $output = (& git.exe ls-remote $Repository "refs/tags/$Tag" 2>$null | Out-String).Trim()
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $savedErrorActionPreference
    $observedCommit = if ($output) { ($output -split "\s+")[0] } else { $null }
    return [ordered]@{
        available = $exitCode -eq 0 -and $observedCommit -eq $ExpectedCommit
        tag = $Tag
        expected_commit = $ExpectedCommit
        observed_commit = $observedCommit
    }
}

$os = Get-CimInstance Win32_OperatingSystem
$computer = Get-CimInstance Win32_ComputerSystem
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
$isAdministrator = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$dataDrive = Get-PSDrive -Name D -ErrorAction SilentlyContinue
$vswhere = "C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe"
$postgresServices = @(Get-Service -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -match "postgres" -or $_.DisplayName -match "PostgreSQL"
})
$postgresDirectory = "C:\Program Files\PostgreSQL"

$installerUrl = "https://get.enterprisedb.com/postgresql/postgresql-18.6-1-windows-x64.exe"
$binariesUrl = "https://get.enterprisedb.com/postgresql/postgresql-18.6-1-windows-x64-binaries.zip"
$pgvectorTag = "v0.8.6"
$pgvectorCommit = "8ee86c96f0fd72390f890aa8a336fda6d3ab4c6c"
$psqlStatus = Get-CommandStatus "psql.exe"
$pgConfigStatus = Get-CommandStatus "pg_config.exe"
$postgresStatus = Get-CommandStatus "postgres.exe"
$gitStatus = Get-CommandStatus "git.exe"
$clStatus = Get-CommandStatus "cl.exe"
$nmakeStatus = Get-CommandStatus "nmake.exe"
$installerStatus = Test-HeadRequest $installerUrl
$binariesStatus = Test-HeadRequest $binariesUrl
$pgvectorTagStatus = Test-GitTag `
    -Repository "https://github.com/pgvector/pgvector.git" `
    -Tag $pgvectorTag `
    -ExpectedCommit $pgvectorCommit
$postgresqlInstalled = $psqlStatus.available -or $postgresStatus.available -or $postgresServices.Count -gt 0 -or (Test-Path -LiteralPath $postgresDirectory -PathType Container)
$toolchainReady = $clStatus.available -and $nmakeStatus.available

$report = [ordered]@{
    checked_at_utc = [DateTime]::UtcNow.ToString("o")
    platform = [ordered]@{
        caption = $os.Caption
        version = $os.Version
        build_number = $os.BuildNumber
        architecture = $os.OSArchitecture
        logical_processors = $computer.NumberOfLogicalProcessors
        memory_gb = [math]::Round($computer.TotalPhysicalMemory / 1GB, 2)
        data_drive_free_gb = if ($dataDrive) { [math]::Round($dataDrive.Free / 1GB, 2) } else { $null }
        is_administrator = $isAdministrator
    }
    local_state = [ordered]@{
        psql = $psqlStatus
        pg_config = $pgConfigStatus
        postgres = $postgresStatus
        postgres_service_count = $postgresServices.Count
        standard_postgres_directory_exists = Test-Path -LiteralPath $postgresDirectory -PathType Container
        git = $gitStatus
        cl = $clStatus
        nmake = $nmakeStatus
        vswhere_available = Test-Path -LiteralPath $vswhere -PathType Leaf
    }
    official_assets = [ordered]@{
        postgresql_installer = $installerStatus
        postgresql_binaries = $binariesStatus
        pgvector = [ordered]@{
            repository = "https://github.com/pgvector/pgvector.git"
            tag_check = $pgvectorTagStatus
            postgresql_18_windows_build_documented = $true
        }
    }
    assessment = [ordered]@{
        postgresql_installed = $postgresqlInstalled
        postgresql_assets_available = $installerStatus.available -and $binariesStatus.available
        pgvector_source_available = $pgvectorTagStatus.available
        windows_build_toolchain_ready = $toolchainReady
        status = if ($toolchainReady) { "READY_FOR_INSTALLATION" } else { "READY_FOR_ASSET_PREPARATION" }
    }
}

$json = $report | ConvertTo-Json -Depth 8
if ($OutputPath) {
    $directory = Split-Path -Parent $OutputPath
    if ($directory) {
        New-Item -ItemType Directory -Force -Path $directory | Out-Null
    }
    $json | Set-Content -LiteralPath $OutputPath -Encoding UTF8
}
$json
