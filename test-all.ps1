$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

function Test-PythonService {
    param([string]$Directory)

    $service = Join-Path $root $Directory
    $python = Join-Path $service ".venv\Scripts\python.exe"
    if (-not (Test-Path $python)) {
        python -m venv (Join-Path $service ".venv")
    }
    & $python -m pip install --disable-pip-version-check -q -r (Join-Path $service "requirements-test.txt")
    if ($LASTEXITCODE -ne 0) {
        throw "$Directory dependencies failed to install"
    }
    Push-Location $service
    try {
        & $python -m pytest -q
        if ($LASTEXITCODE -ne 0) {
            throw "$Directory tests failed"
        }
    } finally {
        Pop-Location
    }
}

Test-PythonService "python-engine"
Test-PythonService "python-xml-engine"

Push-Location (Join-Path $root "java-api")
try {
    mvn test
    if ($LASTEXITCODE -ne 0) {
        throw "Java gateway tests failed"
    }
} finally {
    Pop-Location
}

docker compose --project-directory $root config --quiet
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose configuration is invalid"
}

Write-Host "All service tests passed."
