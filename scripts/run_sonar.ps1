param(
    [switch]$WaitQualityGate,
    [int]$QualityGateTimeoutSec = 300,
    [switch]$SkipCoverage
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Import-DotEnvFile {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "No se encontro archivo .env en: $Path"
    }

    foreach ($rawLine in Get-Content -LiteralPath $Path) {
        $line = $rawLine.Trim()
        if (-not $line) { continue }
        if ($line.StartsWith("#")) { continue }
        $idx = $line.IndexOf("=")
        if ($idx -le 0) { continue }

        $name = $line.Substring(0, $idx).Trim()
        $value = $line.Substring($idx + 1).Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }

        Set-Item -Path "Env:$name" -Value $value
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Import-DotEnvFile -Path (Join-Path $repoRoot ".env")
$qualityOutDir = Join-Path $repoRoot "artifacts\quality\sonar\latest"
New-Item -ItemType Directory -Path $qualityOutDir -Force | Out-Null

$required = @(
    "SONAR_HOST_URL",
    "SONAR_TOKEN",
    "SONAR_PROJECT_KEY",
    "SONAR_ORGANIZATION"
)

$missing = @()
foreach ($name in $required) {
    $value = [Environment]::GetEnvironmentVariable($name)
    if ([string]::IsNullOrWhiteSpace($value)) {
        $missing += $name
    }
}
if ($missing.Count -gt 0) {
    throw ("Faltan variables Sonar en .env: " + ($missing -join ", "))
}

$scanner = Get-Command pysonar -ErrorAction SilentlyContinue
if (-not $scanner) {
    $fallback = Join-Path $repoRoot "venv\Scripts\pysonar.exe"
    if (Test-Path -LiteralPath $fallback) {
        $scanner = @{ Source = $fallback }
    } else {
        throw "No se encontro pysonar en PATH ni en venv\\Scripts\\pysonar.exe"
    }
}

$pythonExe = Join-Path $repoRoot "venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonExe)) {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCmd) {
        throw "No se encontro python en venv\\Scripts ni en PATH"
    }
    $pythonExe = $pythonCmd.Source
}

$args = @(
    "--sonar-host-url=$env:SONAR_HOST_URL",
    "--sonar-token=$env:SONAR_TOKEN",
    "--sonar-project-key=$env:SONAR_PROJECT_KEY",
    "--sonar-organization=$env:SONAR_ORGANIZATION"
)
if ($WaitQualityGate) {
    $args += "--sonar-qualitygate-wait"
    $args += "--sonar-qualitygate-timeout=$QualityGateTimeoutSec"
}

Push-Location $repoRoot
try {
    if (-not $SkipCoverage) {
        & $pythonExe -c "import coverage" *> $null
        if ($LASTEXITCODE -ne 0) {
            throw "Falta dependencia 'coverage'. Ejecuta: pip install -r requirements.txt"
        }

        & $pythonExe -m coverage erase
        & $pythonExe -m coverage run -m pytest `
            tests/test_auth.py `
            tests/test_problem_reports.py `
            tests/test_email_unsubscribe.py `
            tests/test_email_service.py `
            tests/api/test_questionnaire_runtime_api.py `
            tests/api/test_questionnaire_v2_api.py `
            -q
        if ($LASTEXITCODE -ne 0) {
            throw "pytest bajo coverage fallo con codigo $LASTEXITCODE"
        }

        $coverageXmlPath = Join-Path $qualityOutDir "coverage.xml"
        & $pythonExe -m coverage xml -o $coverageXmlPath
        if ($LASTEXITCODE -ne 0) {
            throw "No se pudo generar coverage.xml"
        }
    }

    & $scanner.Source @args
    if ($LASTEXITCODE -ne 0) {
        throw "pysonar finalizo con codigo $LASTEXITCODE"
    }

    $postRunArtifacts = @(
        ".coverage",
        "sonar_issues.csv",
        "sonar_issues.json"
    )
    foreach ($name in $postRunArtifacts) {
        $sourcePath = Join-Path $repoRoot $name
        if (Test-Path -LiteralPath $sourcePath) {
            Move-Item -LiteralPath $sourcePath -Destination (Join-Path $qualityOutDir $name) -Force
        }
    }
} finally {
    Pop-Location
}
