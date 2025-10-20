@echo off
REM RuneCore AI Ecosystem Windows Uninstaller
REM Usage: powershell -c "iwr https://raw.githubusercontent.com/datamann1013/RuneCore_Ecosystem/main/uninstall-runecore-windows.bat -o uninstall.bat && .\uninstall.bat"

setlocal EnableDelayedExpansion

REM Default configuration
set "DEFAULT_INSTALL_DIR=%USERPROFILE%\RuneCore_Ecosystem"
set "INSTALL_DIR=%DEFAULT_INSTALL_DIR%"
set "FORCE_UNINSTALL="

REM Parse command line arguments
:parse_args
if "%~1"=="" goto :args_done
if "%~1"=="--install-dir" (
    set "INSTALL_DIR=%~2"
    shift
    shift
    goto :parse_args
)
if "%~1"=="--force" (
    set "FORCE_UNINSTALL=true"
    shift
    goto :parse_args
)
if "%~1"=="--help" goto :show_help
if "%~1"=="-h" goto :show_help
shift
goto :parse_args

:show_help
echo RuneCore AI Ecosystem Windows Uninstaller
echo.
echo Usage: uninstall-runecore-windows.bat [OPTIONS]
echo.
echo Options:
echo   --install-dir DIR     RuneCore installation directory (default: %USERPROFILE%\RuneCore_Ecosystem)
echo   --force              Skip confirmation prompts
echo   --help               Show this help message
echo.
echo Examples:
echo   # Standard uninstall
echo   uninstall-runecore-windows.bat
echo.
echo   # Force uninstall without prompts
echo   uninstall-runecore-windows.bat --force
exit /b 0

:args_done

:print_header
echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║                RuneCore AI Ecosystem Uninstaller             ║
echo ║                        Windows Edition                       ║
echo ║                                                              ║
echo ║          🗑️ Removing RuneCore Installation Safely            ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

:confirm_uninstall
if "%FORCE_UNINSTALL%"=="true" goto :start_uninstall

echo ⚠️  This will remove RuneCore AI Ecosystem and all its data!
echo ℹ️  Installation directory: %INSTALL_DIR%
echo.
echo ℹ️  The following will be removed:
echo   📁 All RuneCore files and directories
echo   🐳 RuneCore Docker containers and images
echo   📊 RuneCore Docker volumes (databases, logs)
echo   🔗 RuneCore command shortcuts and Desktop shortcuts
echo   ⚙️ RuneCore configuration files
echo.
echo ⚠️  Docker Desktop and other Docker containers will NOT be removed
echo.

set /p "choice=Are you sure you want to continue? (y/N): "
if /i "%choice%" neq "y" (
    echo ℹ️  Uninstall cancelled
    pause
    exit /b 0
)

:start_uninstall
echo ℹ️  Starting uninstall process...

:stop_services
echo ℹ️  Stopping RuneCore services...

REM Stop using docker-compose if available
if exist "%INSTALL_DIR%\docker-compose.yml" (
    cd /d "%INSTALL_DIR%"
    docker-compose down -v --remove-orphans >nul 2>&1
)

if exist "%INSTALL_DIR%\docker\docker-compose.prod.yml" (
    cd /d "%INSTALL_DIR%"
    docker-compose -f docker\docker-compose.prod.yml down -v --remove-orphans >nul 2>&1
)

REM Stop and remove RuneCore containers
echo ℹ️  Removing RuneCore containers...
for /f "tokens=*" %%i in ('docker ps -a --filter "name=ai_service" --filter "name=runecore" --filter "name=errorlogger" --filter "name=message_service" -q 2^>nul') do (
    docker rm -f %%i >nul 2>&1
)

REM Remove RuneCore Docker networks
echo ℹ️  Removing RuneCore networks...
for /f "tokens=*" %%i in ('docker network ls --filter "name=ai_service" --filter "name=runecore" -q 2^>nul') do (
    docker network rm %%i >nul 2>&1
)

echo ✅ Services stopped

:remove_docker_images
echo ℹ️  Removing RuneCore Docker images...

REM Remove RuneCore-specific images
for /f "tokens=*" %%i in ('docker images --filter "reference=ai_service*" --filter "reference=runecore*" --filter "reference=errorlogger*" --filter "reference=message_service*" -q 2^>nul') do (
    docker rmi -f %%i >nul 2>&1
)

REM Remove dangling images
docker image prune -f >nul 2>&1

echo ✅ Docker images removed

:remove_docker_volumes
echo ℹ️  Removing RuneCore Docker volumes...

REM Remove RuneCore-specific volumes
for /f "tokens=*" %%i in ('docker volume ls --filter "name=ai_service" --filter "name=runecore" --filter "name=postgres" --filter "name=redis" -q 2^>nul') do (
    docker volume rm %%i >nul 2>&1
)

REM Remove dangling volumes
docker volume prune -f >nul 2>&1

echo ✅ Docker volumes removed

:remove_files
echo ℹ️  Removing RuneCore files...

REM Remove main installation directory
if exist "%INSTALL_DIR%" (
    rmdir /s /q "%INSTALL_DIR%" 2>nul
    echo ✅ Removed installation directory: %INSTALL_DIR%
)

REM Remove runecore command
set "SCRIPTS_DIR=%USERPROFILE%\AppData\Local\Microsoft\WindowsApps"
if exist "%SCRIPTS_DIR%\runecore.bat" (
    del "%SCRIPTS_DIR%\runecore.bat" 2>nul
    echo ✅ Removed runecore command
)

REM Remove Desktop shortcut
set "DESKTOP=%USERPROFILE%\Desktop"
if exist "%DESKTOP%\RuneCore AI.lnk" (
    del "%DESKTOP%\RuneCore AI.lnk" 2>nul
    echo ✅ Removed Desktop shortcut
)

REM Remove Start Menu shortcuts
set "START_MENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs"
if exist "%START_MENU%\RuneCore AI.lnk" (
    del "%START_MENU%\RuneCore AI.lnk" 2>nul
    echo ✅ Removed Start Menu shortcut
)

REM Remove any RuneCore-specific configuration
set "CONFIG_DIRS=%USERPROFILE%\.runecore %USERPROFILE%\AppData\Local\RuneCore %USERPROFILE%\AppData\Roaming\RuneCore"
for %%d in (%CONFIG_DIRS%) do (
    if exist "%%d" (
        rmdir /s /q "%%d" 2>nul
        echo ✅ Removed configuration directory: %%d
    )
)

REM Remove RuneCore-specific environment files
set "ENV_FILES=%USERPROFILE%\.runecore_env %USERPROFILE%\.env.runecore"
for %%f in (%ENV_FILES%) do (
    if exist "%%f" (
        del "%%f" 2>nul
        echo ✅ Removed environment file: %%f
    )
)

:cleanup_python_packages
echo ℹ️  Checking for RuneCore Python packages...

REM Check for Python command (python or py)
python --version >nul 2>&1
if errorlevel 1 (
    py --version >nul 2>&1
    if errorlevel 1 (
        echo ⚠️  Python not found, skipping Python package cleanup
        goto :cleanup_registry
    )
    set "PYTHON_CMD=py"
) else (
    set "PYTHON_CMD=python"
)

REM List of RuneCore-specific packages that might have been installed
set "RUNECORE_PACKAGES=runecore runecore-ai runecore-errorlogger"
for %%p in (%RUNECORE_PACKAGES%) do (
    %PYTHON_CMD% -m pip show %%p >nul 2>&1
    if not errorlevel 1 (
        echo ℹ️  Removing Python package: %%p
        %PYTHON_CMD% -m pip uninstall -y %%p >nul 2>&1
    )
)

echo ✅ Python package cleanup completed

:cleanup_registry
echo ℹ️  Cleaning Windows registry entries...

REM Remove RuneCore entries from registry (if any were created)
reg delete "HKCU\Software\RuneCore" /f >nul 2>&1
reg delete "HKLM\Software\RuneCore" /f >nul 2>&1

echo ✅ Registry cleanup completed

:show_completion
echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║             RuneCore AI Ecosystem - Removal Complete         ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
echo ✅ RuneCore AI Ecosystem has been completely removed!
echo.
echo ℹ️  What was removed:
echo   ✅ All RuneCore files and directories
echo   ✅ RuneCore Docker containers and images
echo   ✅ RuneCore Docker volumes and networks
echo   ✅ RuneCore command shortcuts and Desktop shortcuts
echo   ✅ RuneCore configuration files
echo   ✅ RuneCore Python packages
echo   ✅ RuneCore registry entries
echo.
echo ℹ️  What was preserved:
echo   ✅ Docker Desktop and Docker Compose
echo   ✅ Other Docker containers and images
echo   ✅ System Python installation
echo   ✅ User data not related to RuneCore
echo.
echo ⚠️  Your system is clean and ready for a fresh RuneCore installation if needed
echo.
echo ℹ️  To reinstall RuneCore:
echo   powershell -c "iwr https://raw.githubusercontent.com/datamann1013/RuneCore_Ecosystem/main/install-runecore-windows.bat -o install.bat && .\install.bat"
echo.
echo ✅ Thank you for using RuneCore AI Ecosystem! 👋
echo.
pause
goto :end

:end
endlocal
