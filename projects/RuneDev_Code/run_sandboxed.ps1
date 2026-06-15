<#
.SYNOPSIS
    Run RuneDev_Code (runecode) inside Windows Sandbox for OS-level isolation.

.DESCRIPTION
    Generates a Windows Sandbox (.wsb) configuration that maps ONLY the target
    project folder (read-write) and the runecode.exe binary (read-only) into an
    ephemeral, disposable VM. The rest of the host filesystem is invisible.
    The sandbox is destroyed on close, so any damage is contained.

    Requires Windows 10/11 Pro/Enterprise/Education with the "Windows Sandbox"
    optional feature enabled.

.PARAMETER Workspace
    Path to the project the agent may modify. Defaults to the current directory.

.PARAMETER ExtraArgs
    Extra arguments passed to runecode (e.g. --mcp-server).

.EXAMPLE
    .\run_sandboxed.ps1 -Workspace C:\code\my-project
#>
[CmdletBinding()]
param(
    [string]$Workspace = (Get-Location).Path,
    [string[]]$ExtraArgs = @()
)

$ErrorActionPreference = "Stop"

# Resolve paths
$workspaceFull = (Resolve-Path $Workspace).Path
$scriptDir     = Split-Path -Parent $MyInvocation.MyCommand.Path
$exePath       = Join-Path $scriptDir "target\release\runecode.exe"

if (-not (Test-Path $exePath)) {
    throw "runecode.exe not found at $exePath — build first: cargo build --release"
}
$exeDir = Split-Path -Parent $exePath

# The sandbox sees the binary at C:\runecode and the project at C:\workspace
$argLine = ($ExtraArgs -join " ")
$logon   = "cmd.exe /k cd /d C:\workspace && C:\runecode\runecode.exe --dir C:\workspace $argLine"

$wsb = @"
<Configuration>
  <VGpu>Disable</VGpu>
  <Networking>Default</Networking>
  <MappedFolders>
    <MappedFolder>
      <HostFolder>$workspaceFull</HostFolder>
      <SandboxFolder>C:\workspace</SandboxFolder>
      <ReadOnly>false</ReadOnly>
    </MappedFolder>
    <MappedFolder>
      <HostFolder>$exeDir</HostFolder>
      <SandboxFolder>C:\runecode</SandboxFolder>
      <ReadOnly>true</ReadOnly>
    </MappedFolder>
  </MappedFolders>
  <LogonCommand>
    <Command>$logon</Command>
  </LogonCommand>
</Configuration>
"@

$wsbPath = Join-Path $env:TEMP "runecode-sandbox.wsb"
$wsb | Out-File -FilePath $wsbPath -Encoding utf8

Write-Host "Workspace (read-write): $workspaceFull"
Write-Host "Binary    (read-only):  $exeDir"
Write-Host "Launching Windows Sandbox ($wsbPath) ..."
Start-Process -FilePath "WindowsSandbox.exe" -ArgumentList $wsbPath
