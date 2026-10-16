param(
    [Parameter(Mandatory = $true)][string]$DocxPath,
    [Parameter(Mandatory = $true)][string]$PptxPath,
    [Parameter(Mandatory = $true)][string]$OutputPath
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.IO.Compression.FileSystem

function Read-ZipEntryText {
    param([System.IO.Compression.ZipArchive]$Archive, [string]$EntryName)
    $entry = $Archive.GetEntry($EntryName)
    if ($null -eq $entry) { throw "Missing package entry: $EntryName" }
    $reader = New-Object System.IO.StreamReader($entry.Open(), [Text.Encoding]::UTF8)
    try { return $reader.ReadToEnd() } finally { $reader.Dispose() }
}

function Inspect-Docx {
    param([string]$Path)
    $archive = [System.IO.Compression.ZipFile]::OpenRead([IO.Path]::GetFullPath($Path))
    try {
        $documentXml = Read-ZipEntryText -Archive $archive -EntryName "word/document.xml"
        return [ordered]@{
            status = "PASS"
            sha256 = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
            package_entry_count = $archive.Entries.Count
            explicit_page_breaks = ([regex]::Matches($documentXml, 'w:type="page"')).Count
            table_count = ([regex]::Matches($documentXml, '<w:tbl(?:\s|>)')).Count
            inline_shape_count = ([regex]::Matches($documentXml, '<wp:inline(?:\s|>)')).Count
        }
    }
    finally { $archive.Dispose() }
}

function Inspect-Pptx {
    param([string]$Path)
    $archive = [System.IO.Compression.ZipFile]::OpenRead([IO.Path]::GetFullPath($Path))
    try {
        $slideCount = @($archive.Entries | Where-Object { $_.FullName -match '^ppt/slides/slide\d+\.xml$' }).Count
        return [ordered]@{
            status = if ($slideCount -eq 50) { "PASS" } else { "FAIL" }
            sha256 = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
            package_entry_count = $archive.Entries.Count
            slide_count = $slideCount
        }
    }
    finally { $archive.Dispose() }
}

$os = Get-CimInstance Win32_OperatingSystem
$wordPath = "C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE"
$powerPointPath = "C:\Program Files\Microsoft Office\root\Office16\POWERPNT.EXE"
$result = [ordered]@{
    generated_at = [DateTimeOffset]::Now.ToString("o")
    platform = [ordered]@{
        caption = $os.Caption
        version = $os.Version
        architecture = $os.OSArchitecture
    }
    office = [ordered]@{
        word_installed = Test-Path -LiteralPath $wordPath
        powerpoint_installed = Test-Path -LiteralPath $powerPointPath
        status = "BLOCKED_NOT_INSTALLED"
    }
    docx = Inspect-Docx -Path $DocxPath
    pptx = Inspect-Pptx -Path $PptxPath
    status = "PARTIAL_PASS_OFFICE_BLOCKED"
}

if ($result.docx.explicit_page_breaks -ne 99 -or $result.pptx.slide_count -ne 50) {
    $result.status = "FAIL"
}

$parent = Split-Path -Parent ([IO.Path]::GetFullPath($OutputPath))
[IO.Directory]::CreateDirectory($parent) | Out-Null
$result | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
$result | ConvertTo-Json -Depth 6
if ($result.status -eq "FAIL") { exit 1 }
