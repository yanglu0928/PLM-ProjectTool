$ErrorActionPreference = "Stop"
$pocRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$repoRoot = (Resolve-Path (Join-Path $pocRoot "..\..")).Path
$python = Join-Path $repoRoot ".poc-runtime\poc-01\windows-offline\Scripts\python.exe"
$verifier = Join-Path $pocRoot "scripts\verify_ocr_pipeline.py"
$evidenceRoot = Join-Path $pocRoot "evidence\windows-11-ocr"
$tesseract = "C:\Program Files\Tesseract-OCR\tesseract.exe"
$tessdata = Join-Path $repoRoot "artifacts\poc-01\windows\tessdata-best"
$ghostscript = Join-Path $repoRoot "artifacts\poc-01\windows\ghostscript-10.08.0-portable\bin\gswin64c.exe"

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Offline Python environment not found: $python"
}
if (-not (Test-Path -LiteralPath $tesseract -PathType Leaf)) {
    throw "Tesseract not found: $tesseract"
}
if (-not (Test-Path -LiteralPath (Join-Path $tessdata "chi_sim.traineddata") -PathType Leaf)) {
    throw "tessdata_best not prepared; run prepare-tessdata-best.ps1 first"
}
if (-not (Test-Path -LiteralPath $ghostscript -PathType Leaf)) {
    throw "Ghostscript not found; run install-ghostscript-portable.ps1 first"
}

New-Item -ItemType Directory -Force -Path $evidenceRoot | Out-Null
$env:TESSERACT_EXE = $tesseract
$env:TESSDATA_PREFIX = $tessdata
$env:GHOSTSCRIPT_EXE = $ghostscript
$env:PATH = "$(Split-Path -Parent $ghostscript);$env:PATH"
& $python $verifier --output-dir $evidenceRoot --output-type pdfa-2 --deskew
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
