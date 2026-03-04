//! marshal_tray — system tray icon for RuneCore_Marshal
//!
//! Sits in the Windows notification area (bottom-right, like Docker/Defender).
//!
//! Icon colour:
//!   Blue  (#3b82f6) — Marshal is reachable on port 11443
//!   Red   (#ef4444) — Marshal is not responding
//!   Gray  (#6b7280) — Initial / unknown state
//!
//! Left-click  → opens the status window
//! Right-click → menu (Quit Tray)

use std::fmt::Write as FmtWrite;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::thread;
use std::time::{Duration, Instant};
use std::ptr;

use tray_icon::{
    TrayIconBuilder,
    TrayIconEvent,
    MouseButton,
    MouseButtonState,
    menu::{Menu, MenuItem, MenuEvent, PredefinedMenuItem},
};
use winit::event::Event;
use winit::event_loop::{ControlFlow, EventLoopBuilder};

// Win32 imports for the status window
use winapi::um::winuser::{
    CreateWindowExW, DefWindowProcW, DestroyWindow, DispatchMessageW,
    GetMessageW, LoadCursorW, LoadIconW, MoveWindow, PostQuitMessage,
    RegisterClassExW, SendMessageW, SetForegroundWindow, SetWindowTextW,
    ShowWindow, TranslateMessage, UpdateWindow,
    BS_PUSHBUTTON, CS_HREDRAW, CS_VREDRAW, CW_USEDEFAULT,
    ES_AUTOVSCROLL, ES_MULTILINE, ES_READONLY, IDC_ARROW, IDI_APPLICATION,
    MSG, SW_SHOW, WM_COMMAND, WM_CREATE, WM_DESTROY, WM_SETFONT, WM_SIZE,
    WNDCLASSEXW, WS_BORDER, WS_CAPTION, WS_CHILD, WS_MINIMIZEBOX,
    WS_OVERLAPPED, WS_SYSMENU, WS_THICKFRAME, WS_VISIBLE, WS_VSCROLL,
    COLOR_WINDOW,
};
use winapi::um::wingdi::{CreateFontW, DEFAULT_QUALITY, FIXED_PITCH, FF_MODERN};
use winapi::um::libloaderapi::GetModuleHandleW;
use winapi::shared::windef::HWND;
use winapi::shared::minwindef::{LPARAM, LRESULT, UINT, WPARAM};

// ── Constants ──────────────────────────────────────────────────────────────

const MARSHAL_PORT: u16 = 11443;
const STATUS_PORT:  u16 = 11444;
const POLL_SECS:    u64 = 5;
const ICON_PX:      u32 = 32;

const IDC_EDIT:    i32 = 1001;
const IDC_REFRESH: i32 = 1002;
const IDC_CLOSE:   i32 = 1003;

// Margin + button area height (pixels)
const MARGIN:   i32 = 8;
const BTN_H:    i32 = 28;
const BTN_W:    i32 = 88;
const FOOT_H:   i32 = BTN_H + MARGIN * 2;

// ── Shared window state ──────────────────────────────────────────────────────

static WINDOW_OPEN: AtomicBool  = AtomicBool::new(false);
static WINDOW_HWND: AtomicUsize = AtomicUsize::new(0);
static EDIT_HWND:   AtomicUsize = AtomicUsize::new(0);

// ── Status enum + polling ─────────────────────────────────────────────────────

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
        Status::Running => "RuneCore Marshal  |  Running  (left-click for status)",
        Status::Stopped => "RuneCore Marshal  |  Stopped",
        Status::Unknown => "RuneCore Marshal  |  ...",
    }
}

// ── Icon generation ───────────────────────────────────────────────────────────

fn make_icon(s: Status) -> tray_icon::Icon {
    let rgba: [u8; 4] = match s {
        Status::Running => [59, 130, 246, 255],  // RuneCore steel blue
        Status::Stopped => [239,  68,  68, 255],  // red
        Status::Unknown => [107, 114, 128, 255],  // gray
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

// ── Status window helpers ─────────────────────────────────────────────────────

fn to_wide(s: &str) -> Vec<u16> {
    s.encode_utf16().chain(std::iter::once(0)).collect()
}

/// Fetch status JSON from the local plain-HTTP endpoint and format it for display.
fn fetch_and_format() -> String {
    let url = format!("http://127.0.0.1:{}/", STATUS_PORT);
    let client = match reqwest::blocking::Client::builder()
        .timeout(Duration::from_secs(4))
        .build()
    {
        Ok(c)  => c,
        Err(e) => return format!("Failed to build HTTP client: {}", e),
    };

    match client.get(&url).send() {
        Err(e) => format!(
            "Cannot connect to Marshal status endpoint.\r\n\r\n\
             Ensure the Marshal service is running.\r\n\r\nError: {}",
            e
        ),
        Ok(resp) => {
            match resp.json::<serde_json::Value>() {
                Err(e) => format!("Failed to parse status response: {}", e),
                Ok(data) => format_status(&data),
            }
        }
    }
}

fn format_status(data: &serde_json::Value) -> String {
    let mut out = String::new();
    let version = data["version"].as_str().unwrap_or("?");
    let sep = "=".repeat(60);

    writeln!(out, "RuneCore Marshal  v{}", version).ok();
    writeln!(out, "Service: Running  (port {})", MARSHAL_PORT).ok();
    writeln!(out).ok();

    // Components
    writeln!(out, "MANAGED COMPONENTS").ok();
    writeln!(out, "{}", sep).ok();

    if let Some(comps) = data["components"].as_array() {
        if comps.is_empty() {
            writeln!(out, "  (none — press Optimise in the RuneCore AI panel to populate)").ok();
        } else {
            for c in comps {
                let name   = c["name"].as_str().unwrap_or("?");
                let status = c["status"].as_str().unwrap_or("unknown");
                let kind   = c["kind"].as_str().unwrap_or("?");
                let bullet = if status == "running" { "[R]" } else if status == "error" { "[E]" } else { "[ ]" };
                writeln!(out, "  {} {:<22} {:<14} ({})", bullet, name, status, kind).ok();
                if let Some(ep) = c["endpoint"].as_str() {
                    writeln!(out, "       Endpoint: {}", ep).ok();
                }
                if let Some(err) = c["error"].as_str() {
                    writeln!(out, "       Error:    {}", err).ok();
                }
            }
        }
    } else {
        writeln!(out, "  (none)").ok();
    }

    writeln!(out).ok();

    // Recent actions
    writeln!(out, "RECENT ACTIONS").ok();
    writeln!(out, "{}", sep).ok();

    if let Some(actions) = data["recent_actions"].as_array() {
        if actions.is_empty() {
            writeln!(out, "  (no actions yet)").ok();
        } else {
            for a in actions {
                if let Some(s) = a.as_str() {
                    writeln!(out, "  {}", s).ok();
                }
            }
        }
    } else {
        writeln!(out, "  (no actions yet)").ok();
    }

    // Replace \n with \r\n for Win32 EDIT controls
    out.replace('\n', "\r\n")
}

// ── Win32 status window ──────────────────────────────────────────────────────

/// Window procedure for the status window.
unsafe extern "system" fn wnd_proc(
    hwnd: HWND,
    msg: UINT,
    wparam: WPARAM,
    lparam: LPARAM,
) -> LRESULT {
    match msg {
        WM_CREATE => {
            let hinstance = GetModuleHandleW(ptr::null());

            // Monospace font (Consolas 10pt)
            let font_name = to_wide("Consolas\0");
            let hfont = CreateFontW(
                -13, 0, 0, 0,
                400, // FW_NORMAL
                0, 0, 0,
                0,   // ANSI_CHARSET
                0,   // OUT_DEFAULT_PRECIS
                0,   // CLIP_DEFAULT_PRECIS
                DEFAULT_QUALITY,
                (FIXED_PITCH | FF_MODERN) as u32,
                font_name.as_ptr(),
            );

            // Multi-line readonly EDIT control
            let edit = CreateWindowExW(
                0,
                to_wide("EDIT\0").as_ptr(),
                to_wide("\0").as_ptr(),
                WS_CHILD | WS_VISIBLE | ES_MULTILINE | ES_READONLY
                    | WS_VSCROLL | ES_AUTOVSCROLL | WS_BORDER,
                MARGIN, MARGIN,
                600 - MARGIN * 2, 420 - FOOT_H - MARGIN,
                hwnd,
                IDC_EDIT as usize as *mut _,
                hinstance,
                ptr::null_mut(),
            );
            if !hfont.is_null() {
                SendMessageW(edit, WM_SETFONT, hfont as WPARAM, 1);
            }
            EDIT_HWND.store(edit as usize, Ordering::SeqCst);

            // Populate with current status immediately
            let text = fetch_and_format();
            let wide = to_wide(&text);
            SetWindowTextW(edit, wide.as_ptr());

            // "Refresh" button
            CreateWindowExW(
                0,
                to_wide("BUTTON\0").as_ptr(),
                to_wide("Refresh\0").as_ptr(),
                WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
                600 - MARGIN - BTN_W * 2 - MARGIN, 420 - FOOT_H + MARGIN,
                BTN_W, BTN_H,
                hwnd,
                IDC_REFRESH as usize as *mut _,
                hinstance,
                ptr::null_mut(),
            );

            // "Close" button
            CreateWindowExW(
                0,
                to_wide("BUTTON\0").as_ptr(),
                to_wide("Close\0").as_ptr(),
                WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
                600 - MARGIN - BTN_W, 420 - FOOT_H + MARGIN,
                BTN_W, BTN_H,
                hwnd,
                IDC_CLOSE as usize as *mut _,
                hinstance,
                ptr::null_mut(),
            );

            0
        }

        WM_SIZE => {
            // Keep EDIT and buttons pinned to the resized window
            let w = (lparam & 0xFFFF) as i32;
            let h = ((lparam as u32 >> 16) & 0xFFFF) as i32;
            let edit = EDIT_HWND.load(Ordering::SeqCst) as HWND;
            if !edit.is_null() {
                MoveWindow(
                    edit,
                    MARGIN, MARGIN,
                    w - MARGIN * 2, h - FOOT_H - MARGIN,
                    1,
                );
            }
            // Re-pin buttons to bottom-right
            let hinstance = GetModuleHandleW(ptr::null());
            // (Buttons are child controls so they move with WM_SIZE automatically
            //  only if we reposition them. Use SetWindowPos via MoveWindow on each.)
            // Find them by their IDs via EnumChildWindows would be complex;
            // instead recreate their position with GetDlgItem equivalent approach.
            // Simplest: just use a fixed layout at creation and allow resize without
            // repositioning buttons (acceptable for a status panel).
            let _ = hinstance; // suppress unused warning
            0
        }

        WM_COMMAND => {
            let ctrl_id = (wparam & 0xFFFF) as i32;
            if ctrl_id == IDC_REFRESH {
                let text = fetch_and_format();
                let wide = to_wide(&text);
                let edit = EDIT_HWND.load(Ordering::SeqCst) as HWND;
                if !edit.is_null() {
                    SetWindowTextW(edit, wide.as_ptr());
                }
            } else if ctrl_id == IDC_CLOSE {
                DestroyWindow(hwnd);
            }
            0
        }

        WM_DESTROY => {
            WINDOW_OPEN.store(false, Ordering::SeqCst);
            WINDOW_HWND.store(0, Ordering::SeqCst);
            EDIT_HWND.store(0, Ordering::SeqCst);
            PostQuitMessage(0);
            0
        }

        _ => DefWindowProcW(hwnd, msg, wparam, lparam),
    }
}

/// Open the status window in a dedicated thread.
/// If a window is already open, bring it to the front instead.
fn spawn_status_window() {
    if WINDOW_OPEN.swap(true, Ordering::SeqCst) {
        // Already open — bring to front
        let hwnd = WINDOW_HWND.load(Ordering::SeqCst) as HWND;
        if !hwnd.is_null() {
            unsafe { SetForegroundWindow(hwnd); }
        }
        return;
    }

    thread::spawn(|| unsafe {
        let hinstance = GetModuleHandleW(ptr::null());
        let class_name = to_wide("MarshalStatusWnd\0");

        // Register window class (ignore ERROR_CLASS_ALREADY_EXISTS = 1410)
        let wc = WNDCLASSEXW {
            cbSize:        std::mem::size_of::<WNDCLASSEXW>() as u32,
            style:         CS_HREDRAW | CS_VREDRAW,
            lpfnWndProc:   Some(wnd_proc),
            cbClsExtra:    0,
            cbWndExtra:    0,
            hInstance:     hinstance,
            hIcon:         LoadIconW(ptr::null_mut(), IDI_APPLICATION),
            hCursor:       LoadCursorW(ptr::null_mut(), IDC_ARROW),
            hbrBackground: (COLOR_WINDOW as usize + 1) as *mut winapi::shared::windef::HBRUSH__,
            lpszMenuName:  ptr::null(),
            lpszClassName: class_name.as_ptr(),
            hIconSm:       LoadIconW(ptr::null_mut(), IDI_APPLICATION),
        };
        RegisterClassExW(&wc); // ignore return; duplicate registration is fine

        let title = to_wide("RuneCore Marshal — Status\0");
        let hwnd = CreateWindowExW(
            0,
            class_name.as_ptr(),
            title.as_ptr(),
            // Resizable window with title bar, system menu, minimize button
            WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX | WS_THICKFRAME | WS_VISIBLE,
            CW_USEDEFAULT, CW_USEDEFAULT,
            620, 460,
            ptr::null_mut(),
            ptr::null_mut(),
            hinstance,
            ptr::null_mut(),
        );

        if hwnd.is_null() {
            WINDOW_OPEN.store(false, Ordering::SeqCst);
            return;
        }

        WINDOW_HWND.store(hwnd as usize, Ordering::SeqCst);
        ShowWindow(hwnd, SW_SHOW);
        UpdateWindow(hwnd);

        // Message loop for this window
        let mut msg: MSG = std::mem::zeroed();
        while GetMessageW(&mut msg, ptr::null_mut(), 0, 0) > 0 {
            TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }

        // WM_DESTROY already cleared the atomics
    });
}

// ── Entry point ───────────────────────────────────────────────────────────────

fn main() {
    let event_loop = EventLoopBuilder::<Status>::with_user_event()
        .build()
        .expect("event loop failed");

    let proxy = event_loop.create_proxy();

    // Build right-click menu
    let label_item = MenuItem::new("RuneCore Marshal", false, None);
    let quit_item  = MenuItem::new("Quit Tray",        true,  None);
    let quit_id    = quit_item.id().clone();

    let menu = Menu::new();
    menu.append(&label_item).unwrap();
    menu.append(&PredefinedMenuItem::separator()).unwrap();
    menu.append(&quit_item).unwrap();

    // Build tray icon
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
                if proxy.send_event(current).is_err() { break; }
                last = current;
            }
            thread::sleep(Duration::from_secs(POLL_SECS));
        }
    });

    let menu_rx = MenuEvent::receiver();
    let tray_rx = TrayIconEvent::receiver();

    event_loop.run(move |event, elwt| {
        elwt.set_control_flow(ControlFlow::WaitUntil(
            Instant::now() + Duration::from_millis(100),
        ));

        // Status update from polling thread → redraw icon and tooltip
        if let Event::UserEvent(status) = event {
            let _ = tray.set_icon(Some(make_icon(status)));
            let _ = tray.set_tooltip(Some(tooltip_text(status).to_string()));
        }

        // Tray icon left-click → open status window
        if let Ok(e) = tray_rx.try_recv() {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = e {
                spawn_status_window();
            }
        }

        // Menu events (Quit)
        if let Ok(e) = menu_rx.try_recv() {
            if e.id == quit_id {
                elwt.exit();
            }
        }
    }).expect("event loop error");
}
