@echo off
REM Script to run Java API locally without Docker on Windows
REM This script builds the Java application and runs it with proper environment variables

echo ========================================
echo Java API Local Runner
echo ========================================
echo.

REM Check if Java is installed
where java >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Java is not installed or not in PATH
    echo Please install Java 17 or higher from https://adoptium.net/
    echo.
    pause
    exit /b 1
)
echo [OK] Java is installed

REM Check if Maven is installed
where mvn >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Maven is not installed or not in PATH
    echo Please install Apache Maven from https://maven.apache.org/download.cgi
    echo.
    pause
    exit /b 1
)
echo [OK] Maven is installed
echo.

REM Navigate to java-api directory
cd /d "%~dp0"

REM Set default environment variables if not already set
if not defined API_PORT set API_PORT=8080
if not defined PIVOT_ENGINE_BASE_URL set PIVOT_ENGINE_BASE_URL=http://localhost:8000
if not defined XML_API_BASE_URL set XML_API_BASE_URL=http://localhost:8001
if not defined PIVOT_API_PATH set PIVOT_API_PATH=/pivot
if not defined XML_GENERATE_PATH set XML_GENERATE_PATH=/generate-xml
if not defined JAVA_OPTS set JAVA_OPTS=-Xmx512m -Xms256m

echo Configuration:
echo   API_PORT:               %API_PORT%
echo   PIVOT_ENGINE_BASE_URL:  %PIVOT_ENGINE_BASE_URL%
echo   XML_API_BASE_URL:       %XML_API_BASE_URL%
echo   PIVOT_API_PATH:         %PIVOT_API_PATH%
echo   XML_GENERATE_PATH:      %XML_GENERATE_PATH%
echo   JAVA_OPTS:              %JAVA_OPTS%
echo.

REM Check if Python services are running
echo Checking Python services...
echo.

curl -s -f "%PIVOT_ENGINE_BASE_URL%/health" >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [OK] Python Pivot Engine is running at %PIVOT_ENGINE_BASE_URL%
) else (
    echo [WARNING] Python Pivot Engine is NOT running at %PIVOT_ENGINE_BASE_URL%
    echo.
    echo To start Python Pivot Engine:
    echo   cd ..\python-engine
    echo   pip install -r requirements.txt
    echo   python app.py
    echo.
)

curl -s -f "%XML_API_BASE_URL%/health" >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [OK] Python XML Engine is running at %XML_API_BASE_URL%
) else (
    echo [WARNING] Python XML Engine is NOT running at %XML_API_BASE_URL%
    echo.
    echo To start Python XML Engine:
    echo   cd ..\python-xml-engine
    echo   pip install -r requirements.txt
    echo   python app.py
    echo.
)

echo.
echo ========================================
echo Building application...
echo ========================================
echo.

REM Clean and build with Maven
call mvn clean package -DskipTests

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Build failed!
    echo.
    pause
    exit /b 1
)

echo.
echo [OK] Build successful
echo.

REM Find the built JAR
set JAR_FILE=target\xlsx-pivot-gateway.jar

if not exist "%JAR_FILE%" (
    echo [ERROR] JAR file not found at %JAR_FILE%
    echo.
    pause
    exit /b 1
)

echo ========================================
echo Starting Java API server...
echo ========================================
echo.
echo Server will be available at: http://localhost:%API_PORT%
echo.
echo Press Ctrl+C to stop the server
echo.

REM Run the application
java %JAVA_OPTS% -jar "%JAR_FILE%"
