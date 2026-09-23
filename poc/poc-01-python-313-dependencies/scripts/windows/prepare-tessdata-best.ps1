$ErrorActionPreference = "Stop"
$pocRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$repoRoot = (Resolve-Path (Join-Path $pocRoot "..\..")).Path
$sourceData = "C:\Program Files\Tesseract-OCR\tessdata"
$artifactRoot = Join-Path $repoRoot "artifacts\poc-01\windows\tessdata-best"
$modelRevision = "e12c65a915945e4c28e237a9b52bc4a8f39a0cec"
$expectedHashes = @{
    "chi_sim"      = "4fef2d1306c8e87616d4d3e4c6c67faf5d44be3342290cf8f2f0f6e3aa7e735b"
    "chi_sim_vert" = "ea672a78157199c333aa12ec4e74550077689b545df5fc770903716850c8b2e5"
    "eng"          = "8280aed0782fe27257a68ea10fe7ef324ca0f8d85bd2fd145d1c2b560bcb66ba"
    "osd"          = "9cf5d576fcc47564f11265841e5ca839001e7e6f38ff7f7aacf46d15a96b00ff"
}

if (-not (Test-Path -LiteralPath $sourceData -PathType Container)) {
    throw "Tesseract tessdata directory not found: $sourceData"
}

New-Item -ItemType Directory -Force -Path $artifactRoot | Out-Null
Copy-Item -LiteralPath (Join-Path $sourceData "configs") -Destination $artifactRoot -Recurse -Force
Copy-Item -LiteralPath (Join-Path $sourceData "tessconfigs") -Destination $artifactRoot -Recurse -Force

foreach ($language in @("chi_sim", "chi_sim_vert", "eng", "osd")) {
    $uri = "https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/$modelRevision/$language.traineddata"
    $destination = Join-Path $artifactRoot "$language.traineddata"
    Invoke-WebRequest -Uri $uri -OutFile $destination
    $actualHash = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLower()
    if ($actualHash -ne $expectedHashes[$language]) {
        throw "SHA-256 mismatch for $language.traineddata"
    }
}

Get-ChildItem -LiteralPath $artifactRoot -Filter "*.traineddata" -File |
    Get-FileHash -Algorithm SHA256 |
    ForEach-Object { "$($_.Hash.ToLower())  $([IO.Path]::GetFileName($_.Path))" } |
    Set-Content -Encoding ascii (Join-Path $artifactRoot "sha256sums.txt")

Write-Output $artifactRoot
