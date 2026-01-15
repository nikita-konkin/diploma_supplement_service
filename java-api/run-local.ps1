# PowerShell script to run Java API locally without Docker
# This script builds the Java application and runs it with proper environment variables

$ErrorActionPreference = "Stop"

# Colors for output
function Write-Success { Write-Host $args -ForegroundColor Green }
function Write-Warn { Write-Host $args -ForegroundColor Yellow }
function Write-Err { Write-Host $args -ForegroundColor Red }
function Write-Info { Write-Host $args -ForegroundColor Cyan }

Write-Success "=== Java API Local Runner ==="
Write-Host ""

# Check if Java is installed
try {
    $javaVersion = java -version 2>&1 | Select-String "version" | ForEach-Object { $_ -replace '.*"(.*)".*', '$1' }
    Write-Success "✓ Java is installed: $javaVersion"

    # Check if Java version is 17 or higher
    $majorVersion = ($javaVersion -split '\.')[0]
    if ([int]$majorVersion -lt 17) {
        Write-Err "Error: Java 17 or higher is required"
        Write-Host "Current Java version: $javaVersion"
        exit 1
    }
} catch {
    Write-Err "Error: Java is not installed or not in PATH"
    Write-Host "Please install Java 17 or higher from https://adoptium.net/"
    exit 1
}

# Check if Maven is installed
try {
    $mvnVersion = mvn -version 2>&1 | Select-String "Apache Maven" | Select-Object -First 1
    Write-Success "✓ Maven is installed: $mvnVersion"
} catch {
    Write-Err "Error: Maven is not installed or not in PATH"
    Write-Host "Please install Apache Maven from https://maven.apache.org/download.cgi"
    exit 1
}

Write-Host ""

# Navigate to java-api directory
Set-Location $PSScriptRoot

# Set default environment variables if not already set
if (-not $env:API_PORT) { $env:API_PORT = "8080" }
if (-not $env:PIVOT_ENGINE_BASE_URL) { $env:PIVOT_ENGINE_BASE_URL = "http://localhost:8000" }
if (-not $env:XML_API_BASE_URL) { $env:XML_API_BASE_URL = "http://localhost:8001" }
if (-not $env:PIVOT_API_PATH) { $env:PIVOT_API_PATH = "/pivot" }
if (-not $env:XML_GENERATE_PATH) { $env:XML_GENERATE_PATH = "/generate-xml" }
if (-not $env:JAVA_OPTS) { $env:JAVA_OPTS = "-Xmx512m -Xms256m" }

Write-Warn "Configuration:"
Write-Host "  API_PORT:               $env:API_PORT"
Write-Host "  PIVOT_ENGINE_BASE_URL:  $env:PIVOT_ENGINE_BASE_URL"
Write-Host "  XML_API_BASE_URL:       $env:XML_API_BASE_URL"
Write-Host "  PIVOT_API_PATH:         $env:PIVOT_API_PATH"
Write-Host "  XML_GENERATE_PATH:      $env:XML_GENERATE_PATH"
Write-Host "  JAVA_OPTS:              $env:JAVA_OPTS"
Write-Host ""

# Check if Python services are running
Write-Warn "Checking Python services..."

function Test-Service {
    param(
        [string]$Url,
        [string]$Name
    )

    try {
        $response = Invoke-WebRequest -Uri "$Url/health" -Method Get -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            Write-Success "✓ $Name is running at $Url"
            return $true
        }
    } catch {
        Write-Err "✗ $Name is NOT running at $Url"
        return $false
    }
}

$pivotRunning = Test-Service -Url $env:PIVOT_ENGINE_BASE_URL -Name "Python Pivot Engine"
$xmlRunning = Test-Service -Url $env:XML_API_BASE_URL -Name "Python XML Engine"

if (-not $pivotRunning -or -not $xmlRunning) {
    Write-Host ""
    Write-Warn "Warning: Some Python services are not running!"
    Write-Host "The Java API will start, but some features may not work."
    Write-Host ""

    if (-not $pivotRunning) {
        Write-Host "To start Python Pivot Engine:"
        Write-Host "  cd ..\python-engine"
        Write-Host "  python app.py"
        Write-Host ""
    }

    if (-not $xmlRunning) {
        Write-Host "To start Python XML Engine:"
        Write-Host "  cd ..\python-xml-engine"
        Write-Host "  python app.py"
        Write-Host ""
    }

    $continue = Read-Host "Continue anyway? (y/N)"
    if ($continue -ne "y" -and $continue -ne "Y") {
        exit 1
    }
}

Write-Host ""
Write-Warn "Building application..."
Write-Host ""

# Clean and build with Maven
& mvn clean package -DskipTests

if ($LASTEXITCODE -ne 0) {
    Write-Err "Build failed!"
    exit 1
}

Write-Host ""
Write-Success "✓ Build successful"
Write-Host ""

# Find the built JAR
$jarFile = "target\xlsx-pivot-gateway.jar"

if (-not (Test-Path $jarFile)) {
    Write-Err "Error: JAR file not found at $jarFile"
    exit 1
}

Write-Success "Starting Java API server..."
Write-Warn "Server will be available at: http://localhost:$env:API_PORT"
Write-Warn "Press Ctrl+C to stop the server"
Write-Host ""

# Run the application
$javaOptsArray = $env:JAVA_OPTS -split ' '
& java $javaOptsArray -jar $jarFile
