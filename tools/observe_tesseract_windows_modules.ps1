param(
    [Parameter(Mandatory = $true)][string]$RuntimeRoot,
    [Parameter(Mandatory = $true)][string]$InputPath,
    [Parameter(Mandatory = $true)][string]$OutputDir,
    [string]$Language = 'chi_sim+eng'
)

$ErrorActionPreference = 'Stop'
$runtime = (Resolve-Path -LiteralPath $RuntimeRoot).Path
$inputFile = (Resolve-Path -LiteralPath $InputPath).Path
$output = (Resolve-Path -LiteralPath $OutputDir).Path
$executable = Join-Path $runtime 'tesseract.exe'
$tessdata = Join-Path $runtime 'tessdata'
if (-not (Test-Path -LiteralPath $executable -PathType Leaf) -or
    -not (Test-Path -LiteralPath $tessdata -PathType Container)) {
    throw 'Fixed Tesseract runtime is incomplete'
}
if ($Language -notmatch '^[a-z_+]+$') { throw 'Language argument rejected' }
$report = Join-Path $output 'module-observation.json'
$stdout = Join-Path $output 'ocr-stdout.txt'
$stderr = Join-Path $output 'ocr-stderr.txt'
foreach ($path in @($report, $stdout, $stderr)) {
    if (Test-Path -LiteralPath $path) { throw "Output exists: $path" }
}
$env:TESSDATA_PREFIX = $tessdata
$process = Start-Process -FilePath $executable -ArgumentList @('"' + $inputFile + '"', 'stdout', '-l', $Language) `
    -RedirectStandardOutput $stdout -RedirectStandardError $stderr -WindowStyle Hidden -PassThru
$modules = @{}
$samples = 0
$sampleErrors = 0
$deadline = (Get-Date).AddSeconds(120)
while (-not $process.HasExited) {
    try {
        foreach ($module in (Get-Process -Id $process.Id -Module -ErrorAction Stop)) {
            $modules[$module.FileName.ToLowerInvariant()] = $true
        }
        $samples++
    } catch {
        $sampleErrors++
    }
    if ((Get-Date) -ge $deadline) {
        Stop-Process -Id $process.Id -ErrorAction SilentlyContinue
        throw 'Tesseract runtime observation timed out'
    }
    Start-Sleep -Milliseconds 20
    $process.Refresh()
}
$process.WaitForExit()
$rootPrefix = $runtime.TrimEnd('\').ToLowerInvariant() + '\'
$systemPrefix = (Join-Path $env:WINDIR 'System32').TrimEnd('\').ToLowerInvariant() + '\'
$local = @($modules.Keys | Where-Object { $_.StartsWith($rootPrefix) } | Sort-Object)
$system = @($modules.Keys | Where-Object { $_.StartsWith($systemPrefix) } | Sort-Object)
$unexpected = @($modules.Keys | Where-Object {
    -not $_.StartsWith($rootPrefix) -and -not $_.StartsWith($systemPrefix)
} | Sort-Object)
$result = [ordered]@{
    status = 'SAMPLED_ONLY'
    release_eligible = $false
    input_sha256 = (Get-FileHash -LiteralPath $inputFile -Algorithm SHA256).Hash.ToLowerInvariant()
    process_exit_code = $process.ExitCode
    sample_count = $samples
    sample_errors = $sampleErrors
    local_modules = @($local | ForEach-Object { [IO.Path]::GetFileName($_) })
    system_module_count = $system.Count
    unexpected_module_paths = $unexpected
    limitation = 'Periodic sampling can miss short-lived or untested input-path loads'
}
$result | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $report -Encoding utf8
Write-Output ($result | ConvertTo-Json -Depth 6 -Compress)
if ($process.ExitCode -ne 0 -or $samples -eq 0) { exit 1 }
