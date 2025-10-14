@echo off
:: AI Service Startup Script for Windows
:: Automatically starts ErrorLogger, Backend, and Frontend services

setlocal enabledelayedexpansion

:: Configuration
set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%
set VENV_PATH=%PROJECT_ROOT%venv
set ERRORLOGGER_DIR=%PROJECT_ROOT%projects\ErrorLogger
set BACKEND_DIR=%PROJECT_ROOT%projects\ai_service\backend
set FRONTEND_DIR=%PROJECT_ROOT%projects\ai_service\frontend

:: Default ports
set ERRORLOGGER_PORT=5001
set BACKEND_PORT=5000
set FRONTEND_PORT=3000

:: PIDs storage
set PIDS_FILE=%PROJECT_ROOT%.service_pids

echo [AI-SERVICE] Starting AI Service Platform
echo =======================================

:: Check if virtual environment exists
if not exist "%VENV_PATH%" (
    echo ERROR: Virtual environment not found at %VENV_PATH%
    echo Please run install.sh first to set up the environment
    pause
    exit /b 1
)

:: Activate virtual environment
echo [AI-SERVICE] Activating virtual environment...
call "%VENV_PATH%\Scripts\activate.bat"

:: Function to check if port is in use (Windows)
:: Note: This is simplified - in practice you'd use netstat or PowerShell

:: Start ErrorLogger
echo [AI-SERVICE] Starting ErrorLogger service...
cd /d "%ERRORLOGGER_DIR%"
start "ErrorLogger" cmd /c "python error_server.py --debug > errorlogger.log 2>&1"
timeout /t 3 /nobreak

:: Start Backend
echo [AI-SERVICE] Starting AI Service Backend...
cd /d "%BACKEND_DIR%"
start "AI Backend" cmd /c "python app.py --debug --skip-model-download > backend.log 2>&1"
timeout /t 5 /nobreak

:: Start Frontend (if npm is available)
echo [AI-SERVICE] Starting Frontend...
cd /d "%FRONTEND_DIR%"
where npm >nul 2>nul
if %errorlevel% equ 0 (
    if not exist "node_modules" (
        echo [AI-SERVICE] Installing frontend dependencies...
        npm install
    )
    start "AI Frontend" cmd /c "npm start > frontend.log 2>&1"
) else (
    echo WARNING: npm not found. Please install Node.js to run the frontend.
)

echo.
echo SUCCESS: AI Service Platform started!
echo.
echo URLs:
echo   Frontend: http://localhost:%FRONTEND_PORT%
echo   Backend API: http://localhost:%BACKEND_PORT%
echo   ErrorLogger: http://localhost:%ERRORLOGGER_PORT%
echo.
echo Press any key to exit...
pause
