param(
    [Parameter(Mandatory = $true)][string]$DocxPath,
    [Parameter(Mandatory = $true)][string]$PptxPath,
    [Parameter(Mandatory = $true)][string]$OutputDirectory
)

$ErrorActionPreference = "Stop"
$outputRoot = [System.IO.Path]::GetFullPath($OutputDirectory)
[System.IO.Directory]::CreateDirectory($outputRoot) | Out-Null
$result = [ordered]@{
    generated_at = [DateTimeOffset]::Now.ToString("o")
    platform = [ordered]@{ system = "Windows"; version = [Environment]::OSVersion.Version.ToString(); machine = $env:PROCESSOR_ARCHITECTURE }
    word = [ordered]@{ status = "NOT_RUN" }
    powerpoint = [ordered]@{ status = "NOT_RUN" }
}

$word = $null
$document = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $document = $word.Documents.Open([System.IO.Path]::GetFullPath($DocxPath), $false, $true)
    $pageCount = $document.ComputeStatistics(2)
    $pdfPath = Join-Path $outputRoot "poc06-word-office.pdf"
    $document.ExportAsFixedFormat($pdfPath, 17)
    $result.word = [ordered]@{
        status = if ($pageCount -eq 100) { "PASS" } else { "FAIL" }
        version = $word.Version
        page_count = $pageCount
        table_count = $document.Tables.Count
        inline_shape_count = $document.InlineShapes.Count
        pdf_size_bytes = (Get-Item -LiteralPath $pdfPath).Length
    }
}
catch {
    $result.word = [ordered]@{ status = "FAIL"; error_type = $_.Exception.GetType().Name; message = $_.Exception.Message }
}
finally {
    if ($null -ne $document) { $document.Close($false) }
    if ($null -ne $word) { $word.Quit() }
    if ($null -ne $document) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($document) }
    if ($null -ne $word) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($word) }
}

$powerpoint = $null
$presentation = $null
try {
    $powerpoint = New-Object -ComObject PowerPoint.Application
    $presentation = $powerpoint.Presentations.Open([System.IO.Path]::GetFullPath($PptxPath), $true, $true, $false)
    $slideCount = $presentation.Slides.Count
    $pdfPath = Join-Path $outputRoot "poc06-ppt-office.pdf"
    $presentation.SaveAs($pdfPath, 32)
    $result.powerpoint = [ordered]@{
        status = if ($slideCount -eq 50) { "PASS" } else { "FAIL" }
        version = $powerpoint.Version
        slide_count = $slideCount
        pdf_size_bytes = (Get-Item -LiteralPath $pdfPath).Length
    }
}
catch {
    $result.powerpoint = [ordered]@{ status = "FAIL"; error_type = $_.Exception.GetType().Name; message = $_.Exception.Message }
}
finally {
    if ($null -ne $presentation) { $presentation.Close() }
    if ($null -ne $powerpoint) { $powerpoint.Quit() }
    if ($null -ne $presentation) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($presentation) }
    if ($null -ne $powerpoint) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($powerpoint) }
}

$result.status = if ($result.word.status -eq "PASS" -and $result.powerpoint.status -eq "PASS") { "PASS" } else { "FAIL" }
$result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $outputRoot "office-open-result.json") -Encoding UTF8
$result | ConvertTo-Json -Depth 8
if ($result.status -ne "PASS") { exit 1 }
