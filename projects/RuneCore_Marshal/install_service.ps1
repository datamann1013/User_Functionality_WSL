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

$ErrorActionPreference = "Stop"
$BinaryPath = "$InstallDir\$BinaryName"
$SourceBinary = "$PSScriptRoot\target\release\$BinaryName"
$ConfigFile   = "$InstallDir\marshal.toml"
$SourceConfig = "$PSScriptRoot\marshal.toml"

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
Write-Host ""
Write-Host "Marshal will auto-start with Windows."
