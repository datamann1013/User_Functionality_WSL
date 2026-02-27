/// tray.rs — Windows system tray icon for RuneSentry.
///
/// Creates a notification-area icon so the daemon shows up alongside Windows
/// Defender, Docker Desktop, etc. The icon persists until the user chooses
/// "Exit" from the right-click context menu or the process is killed.
///
/// This module is compiled only on Windows.

use log::warn;
use tray_icon::{TrayIcon, TrayIconBuilder};
use tray_icon::menu::{Menu, MenuEvent, MenuItem, PredefinedMenuItem};

/// Initialise the tray icon and return the handle.
/// Drop the handle to remove the icon from the tray.
///
/// Spawns a background thread that listens for the "Exit" menu event;
/// when triggered it calls `std::process::exit(0)`.
pub fn setup() -> TrayIcon {
    let icon = make_icon();

    // Build the right-click context menu
    let exit_item = MenuItem::new("Exit RuneSentry", true, None);
    let header   = MenuItem::new("RuneSentry — host monitoring", false, None);

    let menu = Menu::new();
    let _ = menu.append(&header);
    let _ = menu.append(&PredefinedMenuItem::separator());
    let _ = menu.append(&exit_item);

    // Clone the exit-item id so the event thread can compare without holding
    // a reference into the menu that's about to be boxed
    let exit_id = exit_item.id().clone();

    // Background thread: polls the global MenuEvent channel
    std::thread::Builder::new()
        .name("tray-events".into())
        .spawn(move || loop {
            while let Ok(evt) = MenuEvent::receiver().try_recv() {
                if evt.id == exit_id {
                    std::process::exit(0);
                }
            }
            std::thread::sleep(std::time::Duration::from_millis(100));
        })
        .expect("failed to spawn tray event thread");

    TrayIconBuilder::new()
        .with_menu(Box::new(menu))
        .with_tooltip("RuneSentry — host monitoring")
        .with_icon(icon)
        .build()
        .unwrap_or_else(|e| {
            warn!("tray icon creation failed (running headless?): {}", e);
            // Build without menu as a fallback
            TrayIconBuilder::new()
                .with_tooltip("RuneSentry")
                .with_icon(make_icon())
                .build()
                .expect("tray icon fallback also failed")
        })
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
