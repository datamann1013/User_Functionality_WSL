/// tray.rs — Windows system tray icon for RuneSentry.
///
/// Creates a notification-area icon so the daemon shows up alongside Windows
/// Defender, Docker Desktop, etc.  The icon persists until the user chooses
/// "Exit" from the right-click context menu or the process is killed.
///
/// **Why a dedicated thread?**
/// `TrayIconBuilder::build()` creates a hidden HWND on the *calling* thread.
/// Windows only dispatches messages (WM_APP, mouse clicks, etc.) to that HWND
/// when the owning thread pumps its message queue via PeekMessage/DispatchMessage.
/// The main thread spends most of its time in `thread::sleep`, so we run the
/// tray entirely on a separate "tray-pump" thread that loops at 50 ms.
///
/// This module is compiled only on Windows.

use log::warn;
use tray_icon::TrayIconBuilder;
use tray_icon::menu::{Menu, MenuEvent, MenuItem, PredefinedMenuItem};

/// Spawn the tray-pump thread. Returns immediately; the icon lives for the
/// duration of the process (the spawned thread loops forever).
pub fn setup() {
    std::thread::Builder::new()
        .name("tray-pump".into())
        .spawn(|| {
            // Build everything on this thread — TrayIcon owns a thread-local HWND.
            let header    = MenuItem::new("RuneSentry — host monitoring", false, None);
            let exit_item = MenuItem::new("Exit RuneSentry", true, None);

            let menu = Menu::new();
            let _ = menu.append(&header);
            let _ = menu.append(&PredefinedMenuItem::separator());
            let _ = menu.append(&exit_item);

            let exit_id = exit_item.id().clone();

            let _tray = TrayIconBuilder::new()
                .with_menu(Box::new(menu))
                .with_tooltip("RuneSentry — host monitoring")
                .with_icon(make_icon())
                .build()
                .unwrap_or_else(|e| {
                    warn!("tray icon creation failed (running headless?): {}", e);
                    TrayIconBuilder::new()
                        .with_tooltip("RuneSentry")
                        .with_icon(make_icon())
                        .build()
                        .expect("tray icon fallback also failed")
                });

            // Keep MenuItem handles alive for the lifetime of the thread so the
            // menu entries remain valid (muda holds them by Arc, but be explicit).
            let _keep = (header, exit_item, _tray);

            // Pump Windows messages so the hidden HWND receives click events.
            pump_messages(exit_id);
        })
        .expect("failed to spawn tray-pump thread");
}

/// Loop forever: drain the Windows message queue + check for menu events.
///
/// Uses PeekMessageW (non-blocking) so we can also poll the MenuEvent channel
/// at the same cadence without blocking either path.
fn pump_messages(exit_id: tray_icon::menu::MenuId) {
    use windows_sys::Win32::UI::WindowsAndMessaging::{
        DispatchMessageW, PeekMessageW, TranslateMessage, MSG, PM_REMOVE,
    };

    let mut msg: MSG = unsafe { std::mem::zeroed() };

    loop {
        // Check the muda MenuEvent channel first.
        while let Ok(evt) = MenuEvent::receiver().try_recv() {
            if evt.id == exit_id {
                std::process::exit(0);
            }
        }

        // Drain the Win32 message queue for this thread.
        // hwnd=0 means all messages for all windows on this thread.
        unsafe {
            while PeekMessageW(&mut msg, 0, 0, 0, PM_REMOVE) != 0 {
                TranslateMessage(&msg);
                DispatchMessageW(&msg);
            }
        }

        std::thread::sleep(std::time::Duration::from_millis(50));
    }
}

/// Build a minimal 16×16 RGBA icon (solid steel-blue square).
/// A proper .ico file can replace this later.
fn make_icon() -> tray_icon::Icon {
    const W: u32 = 16;
    const H: u32 = 16;
    // Steel blue #3b82f6 = rgb(59, 130, 246)
    let mut rgba = Vec::with_capacity((W * H * 4) as usize);
    for _ in 0..(W * H) {
        rgba.extend_from_slice(&[59u8, 130, 246, 255]);
    }
    tray_icon::Icon::from_rgba(rgba, W, H).expect("tray icon pixel data invalid")
}
