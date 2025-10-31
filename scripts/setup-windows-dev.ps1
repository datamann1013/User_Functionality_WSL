<#
.SYNOPSIS
  Setup developer environment on Windows for RuneCore_Sentinel.

.DESCRIPTION
  Installs Rust (rustup), and either MSVC build tools or MSYS2 + mingw toolchain.
  Use -Toolchain 'msvc' (default) or 'mingw'.

.NOTES
  Run as Administrator for installing system packages. This script is idempotent
  and will skip steps that are already present.
#>

param(
    [ValidateSet('msvc','mingw')]
    [string]$Toolchain = 'msvc'
)

function Ensure-Command {
    param($Name)
    $p = Get-Command $Name -ErrorAction SilentlyContinue
    return $null -ne $p
}

# Import the environment that vcvars64.bat would set into the current PowerShell session.
# vcvars64.bat sets variables for the calling process (cmd.exe). When invoked from PowerShell
# the changes do not persist in the PowerShell environment. This helper runs vcvars64.bat
# inside cmd.exe, captures the environment via `set`, and then applies those variables to
# the current PowerShell process so tools like cl.exe become available.
function Import-VcvarsToPowerShell {
    param(
        [Parameter(Mandatory=$true)]
        [string]$VcvarsPath
    )

    if (-not (Test-Path $VcvarsPath)) {
        Write-Host "vcvars not found at: $VcvarsPath"
        return $false
    }

    Write-Host "Importing environment from: $VcvarsPath"

    # Run cmd.exe, call the batch file, then output the environment with `set`.
    $raw = & cmd.exe /c "`"$VcvarsPath`" && set" 2>$null

    if (-not $raw) {
        Write-Host 'Failed to capture environment from vcvars64.bat'
        return $false
    }

    foreach ($line in $raw) {
        # Each line is NAME=VALUE
        if ($line -match '^(?<name>[^=]+)=(?<value>.*)$') {
            $n = $matches['name']
            $v = $matches['value']
            # Set only if non-empty name
            if ($n) {
                # Update PowerShell process environment
                [System.Environment]::SetEnvironmentVariable($n, $v, 'Process') | Out-Null
            }
        }
    }

    # Verify cl.exe is now available in PATH
    if (Get-Command cl.exe -ErrorAction SilentlyContinue) {
        Write-Host 'Imported vcvars environment successfully; cl.exe is available.'
        return $true
    } else {
        Write-Host 'Imported environment but cl.exe still not found on PATH.'
        return $false
    }
}

Write-Host "Setting up RuneCore Sentinel development environment (toolchain=$Toolchain)"

# Install rustup if missing (attempt download, but handle failures gracefully)
if (-not (Ensure-Command rustup)) {
    Write-Host 'rustup not found - attempting to download and install...'
    $rustup = Join-Path $env:TEMP 'rustup-init.exe'
    try {
        Invoke-WebRequest -Uri 'https://win.rustup.rs/' -OutFile $rustup -UseBasicParsing -ErrorAction Stop
        Write-Host 'Downloaded rustup installer; running...'
        & $rustup -y
        Remove-Item $rustup -Force
        # Ensure Cargo bin is available in the current session
        $cargoBin = Join-Path $env:USERPROFILE ".cargo\bin"
        if (Test-Path $cargoBin) {
            if (-not ($env:PATH -split ';' | Where-Object { $_ -eq $cargoBin })) {
                $env:PATH = $cargoBin + ';' + $env:PATH
                Write-Host "Added $cargoBin to PATH for current session"
            }
        }
    } catch {
        Write-Host 'Failed to download or run rustup installer. This may be a network or DNS issue.'
        Write-Host 'Please install rustup manually from https://rustup.rs/ or run this PowerShell command:'
        Write-Host "    iex ((New-Object System.Net.WebClient).DownloadString('https://win.rustup.rs/'))"
        Write-Host 'After installing rustup, re-open your shell and re-run this script.'
    }
} else {
    Write-Host 'rustup already installed'
}

if ($Toolchain -eq 'msvc') {
    Write-Host 'Configuring MSVC toolchain (recommended on Windows)'
    # Ensure MSVC toolchain exists for rustup
    if (Ensure-Command rustup) {
        & rustup default stable-x86_64-pc-windows-msvc
    } else {
        Write-Host 'rustup not available; skipping rustup toolchain configuration. Install rustup and run: rustup default stable-x86_64-pc-windows-msvc'
    }

    # Suggest installing Visual Studio Build Tools if cl.exe missing
    if (-not (Ensure-Command cl)) {
        Write-Host "cl.exe not found in the current session. Attempting to locate vcvars64.bat and import environment..."
        $vc = Get-ChildItem 'C:\Program Files (x86)\Microsoft Visual Studio' -Recurse -Filter 'vcvars64.bat' -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
        if ($vc) {
            Write-Host "Found vcvars: $vc; attempting to import into PowerShell session..."
            try {
                $ok = Import-VcvarsToPowerShell -VcvarsPath $vc
                if ($ok) {
                    Write-Host 'MSVC environment imported; cl.exe should now be available.'
                } else {
                    Write-Host 'Failed to enable cl.exe from vcvars. You may need to open "x64 Native Tools Command Prompt for VS 2022" or run the following in cmd:'
                    Write-Host "    `"$vc`" && set"
                    Write-Host "Or re-open a Developer Command Prompt and run this script again."
                }
            } catch {
                Write-Host "Error while importing vcvars: $_"
                Write-Host 'If this fails, open the "x64 Native Tools Command Prompt for VS 2022" from the Start Menu and re-run tests there.'
            }
        } else {
            Write-Host "vcvars64.bat not found under 'C:\Program Files (x86)\Microsoft Visual Studio'."
            Write-Host "Please install Visual Studio Build Tools (C++). You can install with winget: winget install --id Microsoft.VisualStudio.2022.BuildTools -e"
            Write-Host "Alternatively, open the 'x64 Native Tools Command Prompt for VS 2022' from Start Menu and re-run this script."
        }
    } else {
        Write-Host "MSVC build tools detected"
    }
} else {
    Write-Host "Configuring MSYS2 + mingw (GNU) toolchain"
    # Ensure MSYS2 is present; if not, try to install via winget
    if (-not (Test-Path "$env:ProgramFiles\MSYS2")) {
        if (Ensure-Command winget) {
            Write-Host "Installing MSYS2 via winget..."
            winget install --id=MSYS2.MSYS2 -e --silent
        } else {
            Write-Host "Please install MSYS2 from https://www.msys2.org/ and re-run this script"
        }
    }

    Write-Host "Please run the MSYS2 shell and run: pacman -Syu; pacman -S --needed base-devel mingw-w64-x86_64-toolchain"
    Write-Host "After MSYS2 toolchain is installed, install the GNU Rust toolchain:"
    Write-Host "    rustup toolchain install stable-x86_64-pc-windows-gnu"
    Write-Host "    rustup default stable-x86_64-pc-windows-gnu"
}

Write-Host 'Installing recommended cargo components (clippy, fmt)'
if (Ensure-Command rustup) {
    try { & rustup component add rustfmt } catch { Write-Host 'rustfmt component add failed' }
    try { & rustup component add clippy } catch { Write-Host 'clippy component add failed' }
} else {
    Write-Host 'rustup not present; skipping cargo components installation.'
}

Write-Host "Windows dev setup complete. Verify by opening a new shell and running: cargo --version"

# Offer to add a safe auto-import snippet to the user's PowerShell profile.
try {
        $resp = Read-Host "Would you like to add an automatic vcvars import to your PowerShell profile for this repo? (Y/n)"
        if ([string]::IsNullOrWhiteSpace($resp) -or $resp -match '^[Yy]') {
                $snippet = @'
function Import-RepoVcvarsIfNeeded {
    try {
        # Ensure rustup/cargo shims are first in PATH so rustup-managed toolchains are used
        $cargoBin = Join-Path $env:USERPROFILE '.cargo\bin'
        if (Test-Path $cargoBin) {
            $parts = $env:Path -split ';' | Where-Object { $_ -ne '' }
            if ($parts[0] -ne $cargoBin) {
                # Remove any existing entries equal to cargoBin then prepend
                $parts = $parts | Where-Object { $_ -ne $cargoBin }
                $env:Path = ($cargoBin + ';' + ($parts -join ';'))
            }
        }

        if ($env:RUNECORE_AUTO_VCVARS -ne '1' -and -not ($PWD.Path -like '*gitproj\RuneCore_Ecosystem*')) { return }
        $vc = Get-ChildItem 'C:\Program Files (x86)\Microsoft Visual Studio' -Recurse -Filter 'vcvars64.bat' -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
        if ($vc) {
            $raw = & cmd.exe /c "`"$vc`" && set" 2>$null
            foreach ($l in $raw) {
                if ($l -match '^(?<n>[^=]+)=(?<v>.*)$') {
                    [System.Environment]::SetEnvironmentVariable($matches['n'], $matches['v'], 'Process') | Out-Null
                }
            }
        }
    } catch {}
}
Import-RepoVcvarsIfNeeded
'@

                if (-not (Test-Path -Path $PROFILE)) { New-Item -Type File -Path $PROFILE -Force | Out-Null }
                Add-Content -Path $PROFILE -Value $snippet
                Write-Host "Appended vcvars auto-import snippet to $PROFILE. Open a new PowerShell to apply."
                Write-Host "You can also enable it for all shells by setting: [System.Environment]::SetEnvironmentVariable('RUNECORE_AUTO_VCVARS','1','User')"
        } else {
                Write-Host 'Skipping profile modification. You can enable auto-import later by running the setup script again.'
        }
} catch {
        Write-Host "Error while attempting to update profile: $_"
}

# Offer to set rustup override for the Sentinel project to MSVC and optionally run cargo test
try {
    if (Ensure-Command rustup) {
        $projPath = Resolve-Path (Join-Path $PSScriptRoot '..\projects\RuneCore_Sentinel')
        $resp2 = Read-Host "Would you like to set a rustup override to 'stable-x86_64-pc-windows-msvc' for $projPath? (Y/n)"
        if ([string]::IsNullOrWhiteSpace($resp2) -or $resp2 -match '^[Yy]') {
            try {
                Push-Location $projPath
                Write-Host "Setting rustup override in $projPath..."
                & rustup override set stable-x86_64-pc-windows-msvc
                Write-Host 'Rustup override set.'

                $resp3 = Read-Host "Run 'cargo test' now in $projPath? This may take several minutes. (Y/n)"
                if ([string]::IsNullOrWhiteSpace($resp3) -or $resp3 -match '^[Yy]') {
                    Write-Host 'Running: cargo clean && cargo test'
                    try {
                        & cargo clean
                    } catch { Write-Host 'cargo clean failed or not present: ' $_ }
                    try {
                        & cargo test
                    } catch {
                        Write-Host "cargo test exited with error: $_"
                    }
                } else {
                    Write-Host 'Skipping cargo test.'
                }
            } finally {
                Pop-Location
            }
        } else {
            Write-Host 'Skipping rustup override.'
        }
    } else {
        Write-Host 'rustup not found; cannot set override. Install rustup and re-run this script.'
    }
} catch {
    Write-Host "Error while setting rustup override or running tests: $_"
}
