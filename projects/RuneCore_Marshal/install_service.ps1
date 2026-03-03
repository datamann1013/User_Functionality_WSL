# Register RuneCore_Marshal as a Windows auto-start service via NSSM.
# Run once as Administrator after building the release binary.
#
# Prerequisites:
#   - NSSM on PATH (https://nssm.cc) or provide -NssmPath
#   - Release binary built: cargo build --release
#   - Certs placed in <InstallDir>\certs\
#
# Usage:
#   .\install_service.ps1
#   .\install_service.ps1 -InstallDir "C:\RuneCore\marshal" -NssmPath "C:\tools\nssm.exe"
#   .\install_service.ps1 -Uninstall

param(
    [string]$InstallDir  = "C:\RuneCore\marshal",
    [string]$NssmPath    = "nssm",
    [string]$ServiceName = "RuneCore-Marshal",
    [string]$BinaryName  = "runecore_marshal.exe",
    [switch]$Uninstall
)

# --- Require Administrator ---
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Not running as Administrator - relaunching elevated ..."
    $params = @()
    foreach ($key in $PSBoundParameters.Keys) {
        $val = $PSBoundParameters[$key]
        if ($val -is [switch]) { if ($val) { $params += "-$key" } }
        else { $params += "-$key `"$val`"" }
    }
    $argString = "-ExecutionPolicy Bypass -File `"$PSCommandPath`" " + ($params -join " ")
    Start-Process powershell -ArgumentList $argString -Verb RunAs
    exit
}
# ---

$ErrorActionPreference = "Stop"
$BinaryPath = "$InstallDir\$BinaryName"
$SourceBinary = "$PSScriptRoot\target\release\$BinaryName"
$ConfigFile   = "$InstallDir\marshal.toml"
$SourceConfig = "$PSScriptRoot\marshal.toml"

# --- Ensure NSSM is available ---
if (-not (Get-Command $NssmPath -ErrorAction SilentlyContinue)) {
    Write-Host "NSSM not found on PATH."

    if (Get-Command choco -ErrorAction SilentlyContinue) {
        Write-Host "Chocolatey found - installing NSSM ..."
        choco install nssm -y
        # Refresh PATH in the current session using Chocolatey's helper
        $chocoProfile = "$env:ChocolateyInstall\helpers\chocolateyProfile.psm1"
        if (Test-Path $chocoProfile) { Import-Module $chocoProfile -Force }
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        if (-not (Get-Command $NssmPath -ErrorAction SilentlyContinue)) {
            Write-Host "NSSM installed but still not found on PATH. Open a new PowerShell window and re-run this script."
            exit 1
        }
        Write-Host "NSSM installed successfully."
    } else {
        Write-Host ""
        Write-Host "Chocolatey is not installed. To continue, install Chocolatey first:"
        Write-Host ""
        Write-Host "  Run this in an elevated PowerShell window:"
        Write-Host "  Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))"
        Write-Host ""
        Write-Host "  Then re-run this script."
        exit 1
    }
}
# ---

if ($Uninstall) {
    Write-Host "Stopping and removing service $ServiceName ..."
    & $NssmPath stop $ServiceName 2>$null
    & $NssmPath remove $ServiceName confirm
    Write-Host "Service removed."
    exit 0
}

# Check for binary
if (-not (Test-Path $SourceBinary)) {
    Write-Error "Binary not found at $SourceBinary. Run 'cargo build --release' first."
    exit 1
}

# Create install dir
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
New-Item -ItemType Directory -Force -Path "$InstallDir\certs" | Out-Null
New-Item -ItemType Directory -Force -Path "$InstallDir\logs" | Out-Null

# Copy binary + config
Copy-Item -Force $SourceBinary $BinaryPath
if (Test-Path $SourceConfig) {
    Copy-Item -Force $SourceConfig $ConfigFile
}

# Copy tray companion binary, register for startup, and launch it now
$SourceTray = "$PSScriptRoot\target\release\marshal_tray.exe"
$TrayBin    = "$InstallDir\marshal_tray.exe"
if (Test-Path $SourceTray) {
    Copy-Item -Force $SourceTray $TrayBin
    # Register for auto-start on user login (like Docker Desktop)
    $regKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
    Set-ItemProperty -Path $regKey -Name "RuneCore-Marshal-Tray" -Value $TrayBin
    Write-Host "Tray icon registered for user startup: $TrayBin"
    # Kill any existing tray instance before launching fresh
    Stop-Process -Name "marshal_tray" -ErrorAction SilentlyContinue
    # Launch the tray icon in the current user session (non-elevated, no window)
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $TrayBin
    $startInfo.UseShellExecute = $true
    $startInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    [System.Diagnostics.Process]::Start($startInfo) | Out-Null
    Write-Host "Tray icon launched."
} else {
    Write-Host "Note: marshal_tray.exe not found in release folder - run 'cargo build --release' to build it."
}

Write-Host "Installing service $ServiceName ..."
& $NssmPath install $ServiceName $BinaryPath
& $NssmPath set $ServiceName AppDirectory $InstallDir
& $NssmPath set $ServiceName AppStdout "$InstallDir\logs\marshal.log"
& $NssmPath set $ServiceName AppStderr "$InstallDir\logs\marshal_err.log"
& $NssmPath set $ServiceName AppRotateFiles 1
& $NssmPath set $ServiceName AppRotateBytes 10485760   # 10 MB
& $NssmPath set $ServiceName Start SERVICE_AUTO_START
& $NssmPath set $ServiceName AppEnvironmentExtra "RUST_LOG=info" "MARSHAL_CONFIG=$ConfigFile"

Write-Host "Starting service ..."
& $NssmPath start $ServiceName

Write-Host ""
Write-Host "RuneCore-Marshal installed and started."
Write-Host "  Binary:  $BinaryPath"
Write-Host "  Config:  $ConfigFile"
Write-Host "  Certs:   $InstallDir\certs\  (place marshal.crt, marshal.key, ca.crt here)"
Write-Host "  Logs:    $InstallDir\logs\"
Write-Host "  Tray:    $TrayBin  (starts with Windows login)"
Write-Host ""
Write-Host "Marshal service auto-starts with Windows."
Write-Host "Tray icon appears in notification area after next login (or run marshal_tray.exe now)."
