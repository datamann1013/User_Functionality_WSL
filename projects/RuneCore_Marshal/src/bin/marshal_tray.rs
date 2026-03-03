//! marshal_tray — system tray icon for RuneCore_Marshal
//!
//! Sits in the Windows notification area (bottom-right, like Docker/Defender).
//!
//! Icon colour:
//!   Blue  (#3b82f6) — Marshal is reachable on port 11443
//!   Red   (#ef4444) — Marshal is not responding
//!   Gray  (#6b7280) — Initial / unknown state
//!
//! Right-click menu:  RuneCore Marshal  |  ──  |  Quit Tray

use std::thread;
use std::time::{Duration, Instant};

use tray_icon::{
    TrayIconBuilder,
    menu::{Menu, MenuItem, MenuEvent, PredefinedMenuItem},
};
use winit::event::Event;
use winit::event_loop::{ControlFlow, EventLoopBuilder};

const MARSHAL_PORT: u16 = 11443;
const POLL_SECS: u64    = 5;
const ICON_PX: u32      = 32;

// ── Status ────────────────────────────────────────────────────────────────────

#[derive(Clone, Copy, PartialEq)]
enum Status { Unknown, Running, Stopped }

fn poll_status() -> Status {
    use std::net::{SocketAddr, TcpStream};
    let addr = SocketAddr::from(([127, 0, 0, 1], MARSHAL_PORT));
    match TcpStream::connect_timeout(&addr, Duration::from_secs(2)) {
        Ok(_)  => Status::Running,
        Err(_) => Status::Stopped,
    }
}

fn tooltip_text(s: Status) -> &'static str {
    match s {
        Status::Running => "RuneCore Marshal  |  Running",
        Status::Stopped => "RuneCore Marshal  |  Stopped",
        Status::Unknown  => "RuneCore Marshal  |  ...",
    }
}

// ── Icon generation ───────────────────────────────────────────────────────────

fn make_icon(s: Status) -> tray_icon::Icon {
    // Filled circle, 32×32 RGBA
    let rgba: [u8; 4] = match s {
        Status::Running => [59, 130, 246, 255],  // RuneCore steel blue
        Status::Stopped => [239,  68,  68, 255],  // red
        Status::Unknown  => [107, 114, 128, 255], // gray
    };
    let n = ICON_PX;
    let mut data = vec![0u8; (n * n * 4) as usize];
    let c = n as f32 / 2.0;
    let r = c - 2.0;
    for y in 0..n {
        for x in 0..n {
            let dx = x as f32 - c;
            let dy = y as f32 - c;
            if dx * dx + dy * dy <= r * r {
                let i = ((y * n + x) * 4) as usize;
                data[i..i + 4].copy_from_slice(&rgba);
            }
        }
    }
    tray_icon::Icon::from_rgba(data, n, n).expect("icon creation failed")
}

// ── Entry point ───────────────────────────────────────────────────────────────

fn main() {
    // EventLoop with Status as the user-event type so the polling thread can
    // send state changes to the main thread without sharing TrayIcon.
    let event_loop = EventLoopBuilder::<Status>::with_user_event()
        .build()
        .expect("event loop failed");

    let proxy = event_loop.create_proxy();

    // Build right-click menu
    let label_item = MenuItem::new("RuneCore Marshal", false, None);
    let quit_item  = MenuItem::new("Quit Tray", true, None);
    let quit_id    = quit_item.id().clone();

    let menu = Menu::new();
    menu.append(&label_item).unwrap();
    menu.append(&PredefinedMenuItem::separator()).unwrap();
    menu.append(&quit_item).unwrap();

    // Build tray icon (stays on main thread — TrayIcon is not Send)
    let tray = TrayIconBuilder::new()
        .with_menu(Box::new(menu))
        .with_tooltip(tooltip_text(Status::Unknown))
        .with_icon(make_icon(Status::Unknown))
        .build()
        .expect("failed to create tray icon");

    // Background thread: polls Marshal port, sends status changes via proxy
    thread::spawn(move || {
        let mut last = Status::Unknown;
        loop {
            let current = poll_status();
            if current != last {
                // If the event loop exited, send_event fails — just stop polling
                if proxy.send_event(current).is_err() {
                    break;
                }
                last = current;
            }
            thread::sleep(Duration::from_secs(POLL_SECS));
        }
    });

    let menu_rx = MenuEvent::receiver();

    event_loop.run(move |event, elwt| {
        // Wake up every 100 ms for menu responsiveness without burning CPU
        elwt.set_control_flow(ControlFlow::WaitUntil(
            Instant::now() + Duration::from_millis(100),
        ));

        // Status update from polling thread → redraw icon and tooltip
        if let Event::UserEvent(status) = event {
            let _ = tray.set_icon(Some(make_icon(status)));
            let _ = tray.set_tooltip(Some(tooltip_text(status).to_string()));
        }

        // Menu events (Quit)
        if let Ok(e) = menu_rx.try_recv() {
            if e.id == quit_id {
                elwt.exit();
            }
        }
    }).expect("event loop error");
}
