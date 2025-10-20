@echo off
REM RuneCore AI Ecosystem Windows Installer
REM Usage: powershell -c "iwr https://raw.githubusercontent.com/datamann1013/RuneCore_Ecosystem/main/install-runecore-windows.bat -o install.bat && .\install.bat"

setlocal EnableDelayedExpansion

REM Default configuration
set "REPO_URL=https://github.com/datamann1013/RuneCore_Ecosystem"
set "RAW_URL=https://raw.githubusercontent.com/datamann1013/RuneCore_Ecosystem"
set "DEFAULT_VERSION=main"
set "INSTALL_DIR=%USERPROFILE%\RuneCore_Ecosystem"
set "VERSION="

REM Parse command line arguments
:parse_args
if "%~1"=="" goto :args_done
if "%~1"=="--version" (
    set "VERSION=%~2"
    shift
    shift
    goto :parse_args
)
if "%~1"=="--install-dir" (
    set "INSTALL_DIR=%~2"
    shift
    shift
    goto :parse_args
)
if "%~1"=="--help" goto :show_help
if "%~1"=="-h" goto :show_help
shift
goto :parse_args

:show_help
echo RuneCore AI Ecosystem Windows Installer
echo.
echo Usage: install-runecore-windows.bat [OPTIONS]
echo.
echo Options:
echo   --version VERSION     Version/branch to install (default: main)
echo   --install-dir DIR     Installation directory (default: %USERPROFILE%\RuneCore_Ecosystem)
echo   --help               Show this help message
echo.
echo Available versions:
echo   main                 Latest stable release
echo   AI_service          AI service development branch
echo   experimental        Experimental features
echo   test                Testing branch
echo.
echo Examples:
echo   # Install latest stable
echo   install-runecore-windows.bat
echo.
echo   # Install AI service branch
echo   install-runecore-windows.bat --version AI_service
echo.
echo   # Install to custom directory
echo   install-runecore-windows.bat --install-dir C:\runecore
exit /b 0

:args_done
if "%VERSION%"=="" set "VERSION=%DEFAULT_VERSION%"

:print_header
echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║                 RuneCore AI Ecosystem Installer              ║
echo ║                        Windows Edition                       ║
echo ║                                                              ║
echo ║  🚀 Advanced AI Service Platform with Security-First Design  ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

:check_requirements
echo ℹ️  Checking Windows system requirements...

REM Check for Git
git --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Git is not installed or not in PATH
    echo ℹ️  Please install Git from https://git-scm.com/download/win
    pause
    exit /b 1
)

REM Check for Docker Desktop
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker Desktop is not installed or not running
    echo ℹ️  Please install Docker Desktop from https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

REM Check for Docker Compose
docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker Compose is not available
    echo ℹ️  Please ensure Docker Desktop includes Docker Compose
    pause
    exit /b 1
)

REM Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    py --version >nul 2>&1
    if errorlevel 1 (
        echo ❌ Python is not installed or not in PATH
        echo ℹ️  Please install Python from https://www.python.org/downloads/
        pause
        exit /b 1
    )
    set "PYTHON_CMD=py"
) else (
    set "PYTHON_CMD=python"
)

REM Check for PowerShell (should be available on Windows 10/11)
powershell -Command "Get-Host" >nul 2>&1
if errorlevel 1 (
    echo ❌ PowerShell is not available
    echo ℹ️  PowerShell is required for this installer
    pause
    exit /b 1
)

echo ✅ All requirements satisfied

:download_runecore
echo ℹ️  Downloading RuneCore Ecosystem (version: %VERSION%)...

REM Remove existing installation if it exists
if exist "%INSTALL_DIR%" (
    echo ⚠️  Existing installation found at %INSTALL_DIR%
    set /p "choice=Do you want to remove it and continue? (y/N): "
    if /i "!choice!" neq "y" (
        echo ❌ Installation cancelled
        pause
        exit /b 1
    )
    echo ℹ️  Removing existing installation...
    rmdir /s /q "%INSTALL_DIR%"
)

REM Clone the repository
echo ℹ️  Cloning repository from branch: %VERSION%
git clone --depth 1 --branch "%VERSION%" "%REPO_URL%.git" "%INSTALL_DIR%"

if not exist "%INSTALL_DIR%" (
    echo ❌ Failed to download RuneCore Ecosystem
    pause
    exit /b 1
)

cd /d "%INSTALL_DIR%"
echo ✅ RuneCore Ecosystem downloaded successfully

:setup_environment
echo ℹ️  Setting up RuneCore environment...

REM Create .env file if it doesn't exist
if not exist ".env" (
    echo ℹ️  Creating environment configuration...
    (
        echo # RuneCore AI Ecosystem Configuration - Windows
        echo RUNECORE_VERSION=1.0.0
        echo RUNECORE_ENV=production
        echo RUNECORE_OS=windows
        echo.
        echo # Service Ports
        echo AI_SERVICE_PORT=5000
        echo ERRORLOGGER_PORT=5001
        echo MESSAGE_SERVICE_PORT=5003
        echo FRONTEND_PORT=3000
        echo OLLAMA_PORT=11434
        echo.
        echo # Database Configuration
        echo POSTGRES_DB=runecore_messages
        echo POSTGRES_USER=runecore
        echo POSTGRES_PASSWORD=runecore_secure_2024
        echo DATABASE_URL=postgresql://runecore:runecore_secure_2024@localhost:5432/runecore_messages
        echo.
        echo # Security
        echo JWT_SECRET_KEY=your-super-secret-jwt-key-change-this-in-production
        echo ERRORLOGGER_SECRET=your-errorlogger-secret-key
        echo.
        echo # Redis Configuration
        echo REDIS_URL=redis://localhost:6379/0
        echo.
        echo # Windows-specific paths
        echo RUNECORE_DATA_PATH=%USERPROFILE%\RuneCore_Data
        echo RUNECORE_LOG_PATH=%USERPROFILE%\RuneCore_Data\logs
        echo.
        echo # Logging
        echo LOG_LEVEL=INFO
    ) > .env
    echo ✅ Environment configuration created
)

REM Install Python dependencies if requirements.txt exists
if exist "requirements.txt" (
    echo ℹ️  Installing Python dependencies...
    %PYTHON_CMD% -m pip install --user -r requirements.txt
)

echo ✅ Environment setup completed

:install_runecore
echo ℹ️  Installing RuneCore AI Ecosystem...

REM Run the local install script if it exists (Windows batch version)
if exist "install.bat" (
    echo ℹ️  Running local installation script...
    call install.bat
) else if exist "install.ps1" (
    echo ℹ️  Running PowerShell installation script...
    powershell -ExecutionPolicy Bypass -File install.ps1
) else if exist "INSTALL.md" (
    echo ℹ️  Installation guide available in INSTALL.md
)

REM Download any required models or dependencies
if exist "projects\ai_service\bootstrap\setup_models.py" (
    echo ℹ️  Setting up AI models...
    cd projects\ai_service\bootstrap
    %PYTHON_CMD% setup_models.py
    cd /d "%INSTALL_DIR%"
)

echo ✅ RuneCore installation completed

:create_shortcuts
echo ℹ️  Creating Windows shortcuts...

REM Create a PowerShell script for RuneCore management
set "SCRIPTS_DIR=%USERPROFILE%\AppData\Local\Microsoft\WindowsApps"
if not exist "%SCRIPTS_DIR%" mkdir "%SCRIPTS_DIR%"

REM Create runecore.bat command
(
    echo @echo off
    echo REM RuneCore AI Ecosystem Control Script - Windows
    echo.
    echo set "RUNECORE_DIR=%INSTALL_DIR%"
    echo.
    echo if "%%1"=="start" goto :start
    echo if "%%1"=="stop" goto :stop
    echo if "%%1"=="status" goto :status
    echo if "%%1"=="logs" goto :logs
    echo if "%%1"=="update" goto :update
    echo if "%%1"=="uninstall" goto :uninstall
    echo goto :help
    echo.
    echo :start
    echo echo 🚀 Starting RuneCore AI Ecosystem...
    echo cd /d "%%RUNECORE_DIR%%"
    echo if exist "start_system.bat" ^(
    echo     call start_system.bat
    echo ^) else if exist "start_runecore_enhanced.bat" ^(
    echo     call start_runecore_enhanced.bat
    echo ^) else if exist "docker-compose.yml" ^(
    echo     docker-compose up -d
    echo ^) else ^(
    echo     echo ❌ No start script found
    echo     exit /b 1
    echo ^)
    echo goto :end
    echo.
    echo :stop
    echo echo 🛑 Stopping RuneCore AI Ecosystem...
    echo cd /d "%%RUNECORE_DIR%%"
    echo docker-compose down
    echo goto :end
    echo.
    echo :status
    echo echo 📊 RuneCore Service Status:
    echo docker ps --filter "name=ai_service"
    echo goto :end
    echo.
    echo :logs
    echo echo 📋 RuneCore Logs:
    echo cd /d "%%RUNECORE_DIR%%"
    echo docker-compose logs -f
    echo goto :end
    echo.
    echo :update
    echo echo 🔄 Updating RuneCore...
    echo cd /d "%%RUNECORE_DIR%%"
    echo git pull
    echo goto :end
    echo.
    echo :uninstall
    echo echo 🗑️ Uninstalling RuneCore...
    echo powershell -c "iwr %RAW_URL%/%VERSION%/uninstall-runecore-windows.bat -o uninstall.bat && .\uninstall.bat"
    echo goto :end
    echo.
    echo :help
    echo echo RuneCore AI Ecosystem Control - Windows
    echo echo Usage: runecore {start^|stop^|status^|logs^|update^|uninstall}
    echo echo.
    echo echo Commands:
    echo echo   start      - Start all RuneCore services
    echo echo   stop       - Stop all RuneCore services
    echo echo   status     - Show service status
    echo echo   logs       - Show service logs
    echo echo   update     - Update to latest version
    echo echo   uninstall  - Remove RuneCore completely
    echo echo.
    echo :end
) > "%SCRIPTS_DIR%\runecore.bat"

REM Create Desktop shortcut
set "DESKTOP=%USERPROFILE%\Desktop"
powershell -Command "^
$WshShell = New-Object -comObject WScript.Shell; ^
$Shortcut = $WshShell.CreateShortcut('%DESKTOP%\RuneCore AI.lnk'); ^
$Shortcut.TargetPath = '%SCRIPTS_DIR%\runecore.bat'; ^
$Shortcut.Arguments = 'start'; ^
$Shortcut.WorkingDirectory = '%INSTALL_DIR%'; ^
$Shortcut.Description = 'RuneCore AI Ecosystem'; ^
$Shortcut.Save()"

echo ✅ Shortcuts created: 'runecore' command and Desktop shortcut

:show_completion
echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║             RuneCore AI Ecosystem - Installation Complete    ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
echo ✅ RuneCore AI Ecosystem installation completed!
echo.
echo ℹ️  Installation Details:
echo   📁 Location: %INSTALL_DIR%
echo   🌿 Version: %VERSION%
echo   🐳 Docker: Ready
echo   💻 OS: Windows
echo.
echo ℹ️  Quick Start:
echo   cd "%INSTALL_DIR%"
echo   runecore start                       # Start all services
echo   # Or double-click the Desktop shortcut
echo.
echo ℹ️  Service URLs (after starting):
echo   🌐 Frontend:        http://localhost:3000
echo   🧠 AI Service:      http://localhost:5000
echo   🛡️ Error Logger:    http://localhost:5001
echo   💬 Message Service: http://localhost:5003
echo.
echo ℹ️  Management Commands:
echo   runecore status                      # Check service status
echo   runecore logs                        # View logs
echo   runecore stop                        # Stop services
echo   runecore uninstall                   # Remove completely
echo.
echo ⚠️  Don't forget to configure your .env file for production use!
echo.
echo ✅ Happy coding with RuneCore! 🚀
echo.
pause
goto :end

:end
endlocal
