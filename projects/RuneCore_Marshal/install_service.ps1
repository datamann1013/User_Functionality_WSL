# Register RuneCore_Marshal as a Windows auto-start service via NSSM.
# Run once as Administrator after building the release binary.
#
# Prerequisites:
#   - NSSM on PATH (https://nssm.cc) or provide -NssmPath
#   - Release binary built: cargo build --release
#   - RuneCore_Core running with port 11441 exposed (for cert bootstrap)
#     If Core is not running, gen_dev_certs.sh fallback is used.
#
# Usage:
#   .\install_service.ps1
#   .\install_service.ps1 -InstallDir "C:\RuneCore\marshal" -NssmPath "C:\tools\nssm.exe"
#   .\install_service.ps1 -CoreHttpUrl "http://localhost:11441"
#   .\install_service.ps1 -Uninstall

param(
    [string]$InstallDir   = "C:\RuneCore\marshal",
    [string]$NssmPath     = "nssm",
    [string]$ServiceName  = "RuneCore-Marshal",
    [string]$BinaryName   = "runecore_marshal.exe",
    # Plain HTTP URL for RuneCore_Core's internal port (used for cert bootstrap)
    [string]$CoreHttpUrl  = "http://localhost:11441",
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
$BinaryPath   = "$InstallDir\$BinaryName"
$SourceBinary = "$PSScriptRoot\target\release\$BinaryName"
$ConfigFile   = "$InstallDir\marshal.toml"
$SourceConfig = "$PSScriptRoot\marshal.toml"

# --- Ensure NSSM is available ---
if (-not (Get-Command $NssmPath -ErrorAction SilentlyContinue)) {
    Write-Host "NSSM not found on PATH."

    if (Get-Command choco -ErrorAction SilentlyContinue) {
        Write-Host "Chocolatey found - installing NSSM ..."
        choco install nssm -y
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
    Write-Host "Binary not found at $SourceBinary. Run 'cargo build --release' first."
    exit 1
}

# Create install dirs
New-Item -ItemType Directory -Force -Path $InstallDir           | Out-Null
New-Item -ItemType Directory -Force -Path "$InstallDir\certs"   | Out-Null
New-Item -ItemType Directory -Force -Path "$InstallDir\logs"    | Out-Null

# Copy binary + config
Copy-Item -Force $SourceBinary $BinaryPath
if (Test-Path $SourceConfig) {
    Copy-Item -Force $SourceConfig $ConfigFile
}

# ─── Cert provisioning via RuneCore_Core PKI ─────────────────────────────────
#
# Flow:
#   1. Compute SHA-256 of the binary
#   2. POST /api/v1/pki/native/register  -> bootstrap_token  (15 min TTL)
#   3. runecore_marshal.exe --bootstrap  -> keypair + cert from Core + DPAPI key
#   4. icacls lock the certs/ directory
#
# Falls back to gen_dev_certs.sh if Core is not reachable.

$CertsDir      = "$InstallDir\certs"
$CertSucceeded = $false

Write-Host ""
Write-Host "==> Provisioning TLS certs from RuneCore_Core ..."
Write-Host "    Core HTTP: $CoreHttpUrl"

try {
    # 1. Binary hash
    $BinaryHash = (Get-FileHash $BinaryPath -Algorithm SHA256).Hash.ToLower()
    Write-Host "    SHA-256: $BinaryHash"

    # 2. Register + get bootstrap token
    $RegBody = ConvertTo-Json @{ cn = "runecore_marshal"; binary_hash = $BinaryHash }
    $RegResp = Invoke-RestMethod `
        -Uri         "$CoreHttpUrl/api/v1/pki/native/register" `
        -Method      POST `
        -Body        $RegBody `
        -ContentType "application/json" `
        -TimeoutSec  15

    if (-not $RegResp.ok) { throw "Core registration failed: $($RegResp.error)" }

    $Token = $RegResp.bootstrap_token
    Write-Host "    Bootstrap token received."

    # 3. Bootstrap binary: generate keypair, get cert signed by Core, DPAPI-encrypt key
    Write-Host "    Running bootstrap ..."
    & $BinaryPath --bootstrap `
        --token       $Token `
        --core-url    $CoreHttpUrl `
        --install-dir $InstallDir

    if ($LASTEXITCODE -ne 0) { throw "Bootstrap exited with code $LASTEXITCODE" }

    $CertSucceeded = $true
    Write-Host "    Cert provisioning complete."
    Write-Host "      $CertsDir\marshal.crt"
    Write-Host "      $CertsDir\marshal.key.dpapi  (DPAPI, machine scope)"
    Write-Host "      $CertsDir\ca.crt"

} catch {
    Write-Host ""
    Write-Host "WARNING: Automatic cert provisioning failed:"
    Write-Host "  $_"
    Write-Host ""
    Write-Host "  If RuneCore_Core is running, make sure port 11441 is exposed:"
    Write-Host "    Check docker-compose.dev.yml has '- 11441:11441' under core ports."
    Write-Host ""
    Write-Host "  Dev fallback: generate self-signed certs manually:"
    Write-Host "    bash gen_dev_certs.sh   (Git Bash, from this project directory)"
    Write-Host "  Then restart Marshal:  sc.exe start $ServiceName"
    Write-Host ""
}

# Lock certs directory (whether bootstrapped or manually placed)
if (Test-Path $CertsDir) {
    icacls $CertsDir /inheritance:r /grant "SYSTEM:(OI)(CI)F" /grant "Administrators:(OI)(CI)F" | Out-Null
    Write-Host "==> certs/ ACL: SYSTEM + Administrators only"
}

# ─── Tray companion ──────────────────────────────────────────────────────────

$SourceTray = "$PSScriptRoot\target\release\marshal_tray.exe"
$TrayBin    = "$InstallDir\marshal_tray.exe"
if (Test-Path $SourceTray) {
    Copy-Item -Force $SourceTray $TrayBin
    $regKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
    Set-ItemProperty -Path $regKey -Name "RuneCore-Marshal-Tray" -Value $TrayBin
    Write-Host "Tray icon registered for user startup: $TrayBin"
    Stop-Process -Name "marshal_tray" -ErrorAction SilentlyContinue
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName        = $TrayBin
    $startInfo.UseShellExecute = $true
    $startInfo.WindowStyle     = [System.Diagnostics.ProcessWindowStyle]::Hidden
    [System.Diagnostics.Process]::Start($startInfo) | Out-Null
    Write-Host "Tray icon launched."
} else {
    Write-Host "Note: marshal_tray.exe not found - run 'cargo build --release' to build it."
}

# ─── Install + start service ─────────────────────────────────────────────────

Write-Host ""
Write-Host "Installing service $ServiceName ..."
& $NssmPath install $ServiceName $BinaryPath
& $NssmPath set $ServiceName AppDirectory $InstallDir
& $NssmPath set $ServiceName AppStdout "$InstallDir\logs\marshal.log"
& $NssmPath set $ServiceName AppStderr "$InstallDir\logs\marshal_err.log"
& $NssmPath set $ServiceName AppRotateFiles 1
& $NssmPath set $ServiceName AppRotateBytes 10485760   # 10 MB
& $NssmPath set $ServiceName Start SERVICE_AUTO_START
& $NssmPath set $ServiceName AppEnvironmentExtra "RUST_LOG=info" "MARSHAL_CONFIG=$ConfigFile"

if ($CertSucceeded) {
    Write-Host "Starting service ..."
    & $NssmPath start $ServiceName
    Write-Host ""
    Write-Host "RuneCore-Marshal installed and started."
} else {
    Write-Host ""
    Write-Host "RuneCore-Marshal installed but NOT started (certs missing)."
    Write-Host "  Provision certs first, then:  sc.exe start $ServiceName"
}

Write-Host ""
Write-Host "  Binary:  $BinaryPath"
Write-Host "  Config:  $ConfigFile"
Write-Host "  Certs:   $CertsDir"
Write-Host "  Logs:    $InstallDir\logs\"
Write-Host "  Tray:    $TrayBin"
Write-Host ""
Write-Host "Marshal service auto-starts with Windows."
