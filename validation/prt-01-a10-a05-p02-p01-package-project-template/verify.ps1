$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$frontend = Join-Path $repo "apps\frontend"

function Invoke-Checked([scriptblock]$Command) {
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "validation command failed with exit code $LASTEXITCODE" }
}

Push-Location $frontend
try {
    Invoke-Checked { pnpm exec vitest run src/modules/prototype/api/prototypeReadClient.spec.ts src/modules/prototype/views/ProjectPrototypePackageTemplateViews.spec.ts }
    Invoke-Checked { pnpm test }
    Invoke-Checked { pnpm typecheck }
    Invoke-Checked { pnpm build }
} finally {
    Pop-Location
}

Write-Output "PRT_01_A10_A05_P02_P01_PROJECT_ORGANIZATION_PASS"
