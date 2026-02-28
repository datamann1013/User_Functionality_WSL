/// install.rs — RuneSentry self-uninstall logic.
///
/// Invoked via `RuneSentry --delete`. Prompts the user, then:
///   1. Removes the Windows startup registry entry (HKCU Run key)
///   2. Schedules deletion of the installed binary via a detached PowerShell
///      (Windows won't let a process delete its own .exe while running)
///
/// Source code and build artefacts in the project directory are untouched.

use std::io::{self, BufRead, Write};

pub fn self_uninstall() {
    println!();
    println!("  RuneSentry — Uninstall");
    println!("  ──────────────────────");
    println!("  This will remove:");
    println!("   • The Windows startup entry (login auto-start)");
    let binary_path = std::env::current_exe()
        .unwrap_or_else(|_| std::path::PathBuf::from("RuneSentry.exe"));
    println!("   • Installed binary: {}", binary_path.display());
    println!();
    println!("  Source code and build artefacts are NOT affected.");
    println!();
    print!("  Continue? [y/N] ");
    io::stdout().flush().unwrap();

    let mut response = String::new();
    io::stdin().lock().read_line(&mut response).unwrap();

    if response.trim().to_lowercase() != "y" {
        println!("  Aborted.");
        return;
    }

    println!();

    remove_startup_entry();
    schedule_binary_deletion(&binary_path);

    println!("  RuneSentry uninstalled. Goodbye.");
    println!();
    std::process::exit(0);
}

fn remove_startup_entry() {
    #[cfg(target_os = "windows")]
    {
        let status = std::process::Command::new("reg")
            .args([
                "delete",
                r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run",
                "/v",
                "RuneSentry",
                "/f",
            ])
            .status();

        match status {
            Ok(s) if s.success() => println!("  ✓ Removed Windows startup entry"),
            _ => println!("  (no startup entry found — already removed or never installed)"),
        }
    }

    #[cfg(not(target_os = "windows"))]
    {
        // On Linux/macOS the install script would have created a systemd unit or launchd plist.
        // For now just inform the user.
        println!("  (non-Windows: remove the autostart entry added by manage.sh manually)");
    }
}

fn schedule_binary_deletion(binary_path: &std::path::Path) {
    let path_str = binary_path.display().to_string();

    #[cfg(target_os = "windows")]
    {
        // Detach a PowerShell process that waits 2 s then deletes the file.
        // We cannot delete our own .exe while it is running on Windows.
        let ps_cmd = format!(
            "Start-Sleep -Seconds 2; \
             Remove-Item '{}' -Force -ErrorAction SilentlyContinue",
            path_str.replace('\'', "''") // escape single quotes
        );

        match std::process::Command::new("powershell")
            .args(["-NoProfile", "-WindowStyle", "Hidden", "-Command", &ps_cmd])
            .spawn()
        {
            Ok(_) => println!("  ✓ Binary removal scheduled: {}", path_str),
            Err(e) => {
                println!("  ✗ Could not schedule binary removal: {}", e);
                println!("    Delete manually: {}", path_str);
            }
        }
    }

    #[cfg(not(target_os = "windows"))]
    {
        match std::fs::remove_file(binary_path) {
            Ok(()) => println!("  ✓ Removed binary: {}", path_str),
            Err(e) => {
                println!("  ✗ Could not remove binary: {}", e);
                println!("    Delete manually: {}", path_str);
            }
        }
    }
}
