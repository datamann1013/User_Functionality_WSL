RuneCore Sentinel - Windows Service Installation

This file describes a minimal way to install the sentinel as a Windows Service for beta testing.

Options:
- Use `sc.exe` to register a Windows service that points to the built sentinel binary.
- Use NSSM (Non-Sucking Service Manager) to wrap the binary and provide restart/monitoring.

Example using `sc.exe` (PowerShell as Administrator):

1. Build the release binary (e.g., `C:\build\runecore-sentinel\release\runecore-sentinel.exe`).
2. Create the service:

```powershell
sc.exe create RuneCoreSentinel binPath= "C:\build\runecore-sentinel\release\runecore-sentinel.exe --config C:\ProgramData\RuneCore\sentinel.toml" start= auto
sc.exe description RuneCoreSentinel "RuneCore Sentinel - local system probe"
```

3. Start the service:

```powershell
sc.exe start RuneCoreSentinel
```

Using NSSM (recommended for easier management):
1. Download NSSM and place `nssm.exe` on the PATH.
2. Install service:

```powershell
nssm install RuneCoreSentinel "C:\build\runecore-sentinel\release\runecore-sentinel.exe"
nssm set RuneCoreSentinel AppParameters "--config C:\ProgramData\RuneCore\sentinel.toml"
nssm start RuneCoreSentinel
```

Notes:
- Create a dedicated service user for security where appropriate.
- Provide the `sentinel.toml` config under `%PROGRAMDATA%\RuneCore\` and use appropriate file ACLs.
- For debugging, run the binary from an elevated PowerShell prompt to see logs.
