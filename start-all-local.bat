@echo off
REM Convenience script to start all services locally
REM This opens each service in a new command prompt window

setlocal

echo ========================================
echo Starting All Services Locally
echo ========================================
echo.
echo This will open 3 separate windows:
echo   1. Python Pivot Engine (Port 8000)
echo   2. Python XML Engine (Port 8001)
echo   3. Java API Gateway (Port 8080)
echo.
echo Press Ctrl+C in each window to stop the respective service.
echo Close this window after all services have started.
echo.
pause

REM Get the current directory
set ROOT_DIR=%~dp0

REM Start Python Pivot Engine in a new window
echo Starting Python Pivot Engine...
start "Python Pivot Engine (Port 8000)" cmd /k "cd /d "%ROOT_DIR%python-engine" && echo Installing dependencies... && pip install -r requirements.txt && echo. && echo Starting Python Pivot Engine on port 8000... && echo. && python app.py"

REM Wait a bit before starting next service
timeout /t 3 /nobreak >nul

REM Start Python XML Engine in a new window
echo Starting Python XML Engine...
start "Python XML Engine (Port 8001)" cmd /k "cd /d "%ROOT_DIR%python-xml-engine" && echo Installing dependencies... && pip install -r requirements.txt && echo. && echo Starting Python XML Engine on port 8001... && echo. && python app.py"

REM Wait a bit before starting next service
timeout /t 3 /nobreak >nul

REM Start Java API Gateway in a new window
echo Starting Java API Gateway...
start "Java API Gateway (Port 8080)" cmd /k "cd /d "%ROOT_DIR%java-api" && echo Building and starting Java API Gateway... && echo. && run-local.bat"

echo.
echo ========================================
echo All services are starting up...
echo ========================================
echo.
echo Please wait for all services to fully start (about 30-60 seconds)
echo.
echo Once started, access the application at:
echo   http://localhost:8080
echo.
echo Check health endpoints:
echo   curl http://localhost:8080/health
echo   curl http://localhost:8000/health
echo   curl http://localhost:8001/health
echo.
echo You can close this window now.
echo The services will continue running in their own windows.
echo.
pause
