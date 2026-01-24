@echo off
REM Start only the AI service components (backend, frontend, ollama, ollama_wrapper)
REM This script is for standalone AI development without Memory Core or other services

echo 🤖 Starting RuneCore AI Service (Standalone Mode)
echo ================================================
echo.

REM Get script directory and repo root
set SCRIPT_DIR=%~dp0
set REPO_ROOT=%SCRIPT_DIR%..

REM Ensure the runecore_dev network exists
echo Checking Docker network...
docker network inspect runecore_dev >nul 2>&1
if errorlevel 1 (
    echo Creating runecore_dev network...
    docker network create runecore_dev
)

REM Navigate to AI project directory
cd /d "%REPO_ROOT%\projects\RuneCore_AI"

REM Stop any existing AI containers
echo Stopping any existing AI containers...
docker compose -f docker-compose.dev.yml down 2>nul

REM Build and start AI services
echo.
echo Building and starting AI services (this may take a moment)...
docker compose -f docker-compose.dev.yml up -d --build

REM Wait for services to be healthy
echo.
echo Waiting for services to become healthy...
timeout /t 5 /nobreak >nul

REM Check health
echo.
echo Service Status:
docker ps --filter "name=runecore_ai" --filter "name=runecore-ollama" --format "table {{.Names}}\t{{.Status}}"

REM Test backend connectivity
echo.
echo Testing backend connectivity...
curl -s http://localhost:5000/health >nul 2>&1
if errorlevel 1 (
    echo ❌ Backend is not responding
    echo    Check logs: docker logs runecore_ai-backend-1
) else (
    echo ✅ Backend is healthy
)

REM Test frontend
echo Testing frontend...
curl -s http://localhost:3000 >nul 2>&1
if errorlevel 1 (
    echo ❌ Frontend is not responding
    echo    Check logs: docker logs runecore_ai-frontend-1
) else (
    echo ✅ Frontend is accessible
)

REM Test Ollama
echo Testing Ollama wrapper...
curl -s http://localhost:5002/health >nul 2>&1
if errorlevel 1 (
    echo ❌ Ollama wrapper is not responding
    echo    Check logs: docker logs runecore-ollama-wrapper
) else (
    echo ✅ Ollama wrapper is healthy
)

echo.
echo ✅ AI Service started successfully!
echo.
echo Access points:
echo   Frontend: http://localhost:3000
echo   Backend API: http://localhost:5000
echo   Backend Health: http://localhost:5000/health
echo   Ollama Wrapper: http://localhost:5002
echo.
echo Running in STANDALONE mode with fallback memory (last 10 messages)
echo For persistent memory, start RuneCore_Memory service separately
echo.
echo Useful commands:
echo   View backend logs: docker logs -f runecore_ai-backend-1
echo   View frontend logs: docker logs -f runecore_ai-frontend-1
echo   View ollama logs: docker logs -f runecore-ollama-wrapper
echo   Stop services: cd projects\RuneCore_AI ^&^& docker compose -f docker-compose.dev.yml down
echo.

pause
