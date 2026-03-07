#![windows_subsystem = "windows"]
//! marshal_tray — system tray icon for RuneCore_Marshal
//!
//! Left-click  → RuneCore-themed status window
//! Right-click → menu (Quit Tray)
//!
//! Icon: blue = running, red = stopped, gray = unknown

use std::fmt::Write as FmtWrite;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::thread;
use std::time::{Duration, Instant};
use std::ptr;

use tray_icon::{
    TrayIconBuilder, TrayIconEvent, MouseButton, MouseButtonState,
    menu::{Menu, MenuItem, MenuEvent, PredefinedMenuItem},
};
use winit::event::Event;
use winit::event_loop::{ControlFlow, EventLoopBuilder};

// Win32 — window management
use winapi::um::winuser::{
    CreateWindowExW, DefWindowProcW, DestroyWindow, DispatchMessageW,
    DrawTextW, FillRect, GetClientRect, GetDlgCtrlID, GetDlgItem,
    GetMessageW, GetWindowTextW, LoadCursorW, LoadIconW, MoveWindow,
    PostQuitMessage, RegisterClassExW, SendMessageW, SetForegroundWindow,
    SetWindowTextW, ShowWindow, TranslateMessage, UpdateWindow,
    BS_OWNERDRAW, CS_HREDRAW, CS_VREDRAW, CW_USEDEFAULT,
    DRAWITEMSTRUCT, DT_CENTER, DT_SINGLELINE, DT_VCENTER,
    ES_AUTOVSCROLL, ES_MULTILINE, ES_READONLY,
    IDC_ARROW, IDI_APPLICATION, MSG, ODS_SELECTED,
    SS_CENTER, SS_CENTERIMAGE,
    SW_SHOW, WM_COMMAND, WM_CREATE, WM_CTLCOLOREDIT, WM_CTLCOLORSTATIC,
    WM_DESTROY, WM_DRAWITEM, WM_ERASEBKGND, WM_SETFONT, WM_SIZE,
    WNDCLASSEXW, WS_CAPTION, WS_CHILD, WS_MINIMIZEBOX,
    WS_OVERLAPPED, WS_SYSMENU, WS_THICKFRAME, WS_VISIBLE, WS_VSCROLL,
};
// Win32 — GDI
use winapi::um::wingdi::{
    CreateFontW, CreateSolidBrush, DEFAULT_QUALITY, DeleteObject,
    FIXED_PITCH, FF_MODERN, FW_BOLD, FW_NORMAL, SelectObject,
    SetBkColor, SetBkMode, SetTextColor,
};
use winapi::um::libloaderapi::GetModuleHandleW;
use winapi::shared::windef::{HDC, HGDIOBJ, HBRUSH, HWND, RECT};
use winapi::shared::minwindef::{LPARAM, LRESULT, UINT, WPARAM};

// ── RuneCore colour palette (Win32 BGR order) ────────────────────────────────
//   CSS #rrggbb  →  Win32 COLORREF 0x00BBGGRR
//   --bg:        #111827  →  0x00271811
//   --bg-raised: #1e293b  →  0x003B291E
//   --bg-deep:   #0f172a  →  0x002A170F
//   --accent:    #3b82f6  →  0x00F6823B
//   --text:      #e5e7eb  →  0x00EBE7E5
const C_BG:      u32 = 0x00_27_18_11;
const C_CONTENT: u32 = 0x00_3B_29_1E;
const C_HEADER:  u32 = 0x00_2A_17_0F;
const C_ACCENT:  u32 = 0x00_F6_82_3B;
const C_TEXT:    u32 = 0x00_EB_E7_E5;

// ── Ports / polling ──────────────────────────────────────────────────────────
const MARSHAL_PORT: u16 = 11443;
const STATUS_PORT:  u16 = 11444;
const POLL_SECS:    u64 = 5;
const ICON_PX:      u32 = 32;

// ── Control IDs ──────────────────────────────────────────────────────────────
const IDC_HEADER:      i32 = 1000;
const IDC_HEADER_LINE: i32 = 1001;
const IDC_EDIT:        i32 = 1002;
const IDC_REFRESH:     i32 = 1003;
const IDC_CLOSE:       i32 = 1004;

// ── Layout (pixels) ──────────────────────────────────────────────────────────
const HEADER_H: i32 = 42;   // header bar height
const ACCENT_H: i32 = 3;    // steel-blue stripe height
const TOP_OFF:  i32 = HEADER_H + ACCENT_H;
const MARGIN:   i32 = 8;
const BTN_H:    i32 = 30;
const BTN_W:    i32 = 94;
const FOOT_H:   i32 = BTN_H + MARGIN * 2;

// ── GDI resource globals (created once per window open) ──────────────────────
static BG_BRUSH:      AtomicUsize = AtomicUsize::new(0);
static CONTENT_BRUSH: AtomicUsize = AtomicUsize::new(0);
static HEADER_BRUSH:  AtomicUsize = AtomicUsize::new(0);
static ACCENT_BRUSH:  AtomicUsize = AtomicUsize::new(0);
static MONO_FONT:     AtomicUsize = AtomicUsize::new(0);
static HEADER_FONT:   AtomicUsize = AtomicUsize::new(0);

// ── Window state ─────────────────────────────────────────────────────────────
static WINDOW_OPEN: AtomicBool  = AtomicBool::new(false);
static WINDOW_HWND: AtomicUsize = AtomicUsize::new(0);

// ── GDI lifecycle ────────────────────────────────────────────────────────────

unsafe fn create_gdi_resources() {
    BG_BRUSH.store     (CreateSolidBrush(C_BG)      as usize, Ordering::SeqCst);
    CONTENT_BRUSH.store(CreateSolidBrush(C_CONTENT) as usize, Ordering::SeqCst);
    HEADER_BRUSH.store (CreateSolidBrush(C_HEADER)  as usize, Ordering::SeqCst);
    ACCENT_BRUSH.store (CreateSolidBrush(C_ACCENT)  as usize, Ordering::SeqCst);

    let fname = to_wide("Consolas");
    MONO_FONT.store(CreateFontW(
        -13, 0, 0, 0, FW_NORMAL as i32, 0, 0, 0, 0, 0, 0,
        DEFAULT_QUALITY, (FIXED_PITCH | FF_MODERN) as u32, fname.as_ptr(),
    ) as usize, Ordering::SeqCst);

    HEADER_FONT.store(CreateFontW(
        -15, 0, 0, 0, FW_BOLD as i32, 0, 0, 0, 0, 0, 0,
        DEFAULT_QUALITY, (FIXED_PITCH | FF_MODERN) as u32, fname.as_ptr(),
    ) as usize, Ordering::SeqCst);
}

unsafe fn destroy_gdi_resources() {
    for h in [
        BG_BRUSH.swap(0, Ordering::SeqCst),
        CONTENT_BRUSH.swap(0, Ordering::SeqCst),
        HEADER_BRUSH.swap(0, Ordering::SeqCst),
        ACCENT_BRUSH.swap(0, Ordering::SeqCst),
        MONO_FONT.swap(0, Ordering::SeqCst),
        HEADER_FONT.swap(0, Ordering::SeqCst),
    ] {
        if h != 0 { DeleteObject(h as *mut _); }
    }
}

// ── Status enum + polling ────────────────────────────────────────────────────

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

// ── Tray icon ────────────────────────────────────────────────────────────────

fn make_icon(s: Status) -> tray_icon::Icon {
    let rgba: [u8; 4] = match s {
        Status::Running => [59, 130, 246, 255],
        Status::Stopped => [239,  68,  68, 255],
        Status::Unknown => [107, 114, 128, 255],
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

// ── Status text helpers ───────────────────────────────────────────────────────

fn to_wide(s: &str) -> Vec<u16> {
    s.encode_utf16().chain(std::iter::once(0)).collect()
}

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
             Make sure the Marshal service is running.\r\n\r\nError: {}",
            e
        ),
        Ok(resp) => match resp.json::<serde_json::Value>() {
            Err(e) => format!("Failed to parse status response: {}", e),
            Ok(data) => format_status(&data),
        },
    }
}

fn format_status(data: &serde_json::Value) -> String {
    let mut out = String::new();
    let version = data["version"].as_str().unwrap_or("?");
    let sep = "─".repeat(56);

    writeln!(out, "  RuneCore Marshal  v{}    port {}", version, MARSHAL_PORT).ok();
    writeln!(out, "  Status: Running").ok();
    writeln!(out).ok();

    writeln!(out, "  MANAGED COMPONENTS").ok();
    writeln!(out, "  {}", sep).ok();

    if let Some(comps) = data["components"].as_array() {
        if comps.is_empty() {
            writeln!(out, "  (none — use Optimise in RuneCore Mind to populate)").ok();
        } else {
            for c in comps {
                let name   = c["name"].as_str().unwrap_or("?");
                let status = c["status"].as_str().unwrap_or("unknown");
                let kind   = c["kind"].as_str().unwrap_or("?");
                let bullet = if status == "running" { "●" }
                             else if status == "error" { "✗" }
                             else { "○" };
                writeln!(out, "  {} {:<24} {:<16} ({})", bullet, name, status, kind).ok();
                if let Some(ep) = c["endpoint"].as_str() {
                    writeln!(out, "       endpoint: {}", ep).ok();
                }
                if let Some(err) = c["error"].as_str() {
                    writeln!(out, "       error:    {}", err).ok();
                }
            }
        }
    } else {
        writeln!(out, "  (none)").ok();
    }

    writeln!(out).ok();
    writeln!(out, "  RECENT ACTIONS").ok();
    writeln!(out, "  {}", sep).ok();

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

    out.replace('\n', "\r\n")
}

// ── Win32 window procedure ───────────────────────────────────────────────────

unsafe extern "system" fn wnd_proc(
    hwnd: HWND,
    msg:  UINT,
    wparam: WPARAM,
    lparam: LPARAM,
) -> LRESULT {
    match msg {

        // ── Create all child controls ─────────────────────────────────────
        WM_CREATE => {
            let hi = GetModuleHandleW(ptr::null());
            let mf = MONO_FONT.load(Ordering::SeqCst) as WPARAM;
            let hf = HEADER_FONT.load(Ordering::SeqCst) as WPARAM;

            // Header STATIC — dark header bg, Consolas Bold, centred text
            let header = CreateWindowExW(
                0,
                to_wide("STATIC").as_ptr(),
                to_wide("RuneCore Marshal").as_ptr(),
                WS_CHILD | WS_VISIBLE | SS_CENTER | SS_CENTERIMAGE,
                0, 0, 640, HEADER_H,
                hwnd, IDC_HEADER as usize as *mut _, hi, ptr::null_mut(),
            );
            if !header.is_null() && hf != 0 {
                SendMessageW(header, WM_SETFONT, hf, 1);
            }

            // Steel-blue accent stripe
            CreateWindowExW(
                0,
                to_wide("STATIC").as_ptr(),
                to_wide("").as_ptr(),
                WS_CHILD | WS_VISIBLE,
                0, HEADER_H, 640, ACCENT_H,
                hwnd, IDC_HEADER_LINE as usize as *mut _, hi, ptr::null_mut(),
            );

            // Content EDIT — multi-line, read-only, dark bg
            let edit = CreateWindowExW(
                0,
                to_wide("EDIT").as_ptr(),
                to_wide("").as_ptr(),
                WS_CHILD | WS_VISIBLE | WS_VSCROLL
                    | ES_MULTILINE | ES_READONLY | ES_AUTOVSCROLL,
                MARGIN, TOP_OFF + MARGIN,
                640 - MARGIN * 2, 420 - TOP_OFF - FOOT_H - MARGIN,
                hwnd, IDC_EDIT as usize as *mut _, hi, ptr::null_mut(),
            );
            if !edit.is_null() && mf != 0 {
                SendMessageW(edit, WM_SETFONT, mf, 1);
            }
            // Populate immediately
            let text = fetch_and_format();
            let wide = to_wide(&text);
            SetWindowTextW(edit, wide.as_ptr());

            // Refresh button (owner-draw → steel blue)
            let refresh = CreateWindowExW(
                0,
                to_wide("BUTTON").as_ptr(),
                to_wide("Refresh").as_ptr(),
                WS_CHILD | WS_VISIBLE | BS_OWNERDRAW,
                640 - MARGIN - BTN_W * 2 - MARGIN, 420 - FOOT_H + MARGIN,
                BTN_W, BTN_H,
                hwnd, IDC_REFRESH as usize as *mut _, hi, ptr::null_mut(),
            );
            if !refresh.is_null() && mf != 0 {
                SendMessageW(refresh, WM_SETFONT, mf, 1);
            }

            // Close button (owner-draw → steel blue)
            let close_btn = CreateWindowExW(
                0,
                to_wide("BUTTON").as_ptr(),
                to_wide("Close").as_ptr(),
                WS_CHILD | WS_VISIBLE | BS_OWNERDRAW,
                640 - MARGIN - BTN_W, 420 - FOOT_H + MARGIN,
                BTN_W, BTN_H,
                hwnd, IDC_CLOSE as usize as *mut _, hi, ptr::null_mut(),
            );
            if !close_btn.is_null() && mf != 0 {
                SendMessageW(close_btn, WM_SETFONT, mf, 1);
            }

            0
        }

        // ── Dark window background ────────────────────────────────────────
        WM_ERASEBKGND => {
            let hdc = wparam as HDC;
            let mut rc: RECT = std::mem::zeroed();
            GetClientRect(hwnd, &mut rc);
            let bg = BG_BRUSH.load(Ordering::SeqCst) as HBRUSH;
            if !bg.is_null() { FillRect(hdc, &rc, bg); }
            1
        }

        // ── Colour child controls ─────────────────────────────────────────
        WM_CTLCOLORSTATIC | WM_CTLCOLOREDIT => {
            let hdc     = wparam as HDC;
            let ctrl    = lparam as HWND;
            let ctrl_id = GetDlgCtrlID(ctrl);

            if ctrl_id == IDC_HEADER {
                SetBkMode(hdc, 1); // TRANSPARENT
                SetTextColor(hdc, C_TEXT);
                return HEADER_BRUSH.load(Ordering::SeqCst) as LRESULT;
            }
            if ctrl_id == IDC_HEADER_LINE {
                return ACCENT_BRUSH.load(Ordering::SeqCst) as LRESULT;
            }
            // Content EDIT and any other controls
            SetBkMode(hdc, 2); // OPAQUE
            SetBkColor(hdc, C_CONTENT);
            SetTextColor(hdc, C_TEXT);
            CONTENT_BRUSH.load(Ordering::SeqCst) as LRESULT
        }

        // ── Owner-draw buttons ────────────────────────────────────────────
        WM_DRAWITEM => {
            let dis    = &*(lparam as *const DRAWITEMSTRUCT);
            let hdc    = dis.hDC;
            let rc     = dis.rcItem;
            let pressed = dis.itemState & ODS_SELECTED != 0;

            let brush: HBRUSH = if pressed {
                CONTENT_BRUSH.load(Ordering::SeqCst) as HBRUSH
            } else {
                ACCENT_BRUSH.load(Ordering::SeqCst) as HBRUSH
            };
            FillRect(hdc, &rc, brush);

            let font = MONO_FONT.load(Ordering::SeqCst) as HGDIOBJ;
            let old_font = if !font.is_null() {
                SelectObject(hdc, font)
            } else {
                ptr::null_mut()
            };
            SetBkMode(hdc, 1); // TRANSPARENT
            SetTextColor(hdc, C_TEXT);

            let mut buf = [0u16; 64];
            let n = GetWindowTextW(dis.hwndItem, buf.as_mut_ptr(), 64);
            if n > 0 {
                let mut draw_rc = rc;
                DrawTextW(hdc, buf.as_ptr(), n, &mut draw_rc,
                          DT_CENTER | DT_SINGLELINE | DT_VCENTER);
            }
            if !old_font.is_null() { SelectObject(hdc, old_font); }
            1
        }

        // ── Resize: reposition all controls ──────────────────────────────
        WM_SIZE => {
            let w = (lparam & 0xFFFF) as i32;
            let h = ((lparam as u32 >> 16) & 0xFFFF) as i32;

            macro_rules! mv {
                ($id:expr, $x:expr, $y:expr, $cw:expr, $ch:expr) => {{
                    let wh = GetDlgItem(hwnd, $id);
                    if !wh.is_null() { MoveWindow(wh, $x, $y, $cw, $ch, 1); }
                }};
            }

            mv!(IDC_HEADER,      0, 0, w, HEADER_H);
            mv!(IDC_HEADER_LINE, 0, HEADER_H, w, ACCENT_H);
            mv!(IDC_EDIT,
                MARGIN, TOP_OFF + MARGIN,
                w - MARGIN * 2,
                h - TOP_OFF - FOOT_H - MARGIN);
            mv!(IDC_REFRESH,
                w - MARGIN - BTN_W * 2 - MARGIN,
                h - FOOT_H + MARGIN, BTN_W, BTN_H);
            mv!(IDC_CLOSE,
                w - MARGIN - BTN_W,
                h - FOOT_H + MARGIN, BTN_W, BTN_H);
            0
        }

        // ── Button commands ───────────────────────────────────────────────
        WM_COMMAND => {
            let ctrl_id = (wparam & 0xFFFF) as i32;
            if ctrl_id == IDC_REFRESH {
                let edit = GetDlgItem(hwnd, IDC_EDIT);
                if !edit.is_null() {
                    let text = fetch_and_format();
                    let wide = to_wide(&text);
                    SetWindowTextW(edit, wide.as_ptr());
                }
            } else if ctrl_id == IDC_CLOSE {
                DestroyWindow(hwnd);
            }
            0
        }

        // ── Cleanup ───────────────────────────────────────────────────────
        WM_DESTROY => {
            WINDOW_OPEN.store(false, Ordering::SeqCst);
            WINDOW_HWND.store(0, Ordering::SeqCst);
            destroy_gdi_resources();
            PostQuitMessage(0);
            0
        }

        _ => DefWindowProcW(hwnd, msg, wparam, lparam),
    }
}

// ── Spawn / focus status window ──────────────────────────────────────────────

fn spawn_status_window() {
    if WINDOW_OPEN.swap(true, Ordering::SeqCst) {
        let hwnd = WINDOW_HWND.load(Ordering::SeqCst) as HWND;
        if !hwnd.is_null() {
            unsafe { SetForegroundWindow(hwnd); }
        }
        return;
    }

    thread::spawn(|| unsafe {
        create_gdi_resources();

        let hi         = GetModuleHandleW(ptr::null());
        let class_name = to_wide("MarshalStatusWnd");

        let wc = WNDCLASSEXW {
            cbSize:        std::mem::size_of::<WNDCLASSEXW>() as u32,
            style:         CS_HREDRAW | CS_VREDRAW,
            lpfnWndProc:   Some(wnd_proc),
            cbClsExtra:    0,
            cbWndExtra:    0,
            hInstance:     hi,
            hIcon:         LoadIconW(ptr::null_mut(), IDI_APPLICATION),
            hCursor:       LoadCursorW(ptr::null_mut(), IDC_ARROW),
            hbrBackground: BG_BRUSH.load(Ordering::SeqCst) as HBRUSH,
            lpszMenuName:  ptr::null(),
            lpszClassName: class_name.as_ptr(),
            hIconSm:       LoadIconW(ptr::null_mut(), IDI_APPLICATION),
        };
        RegisterClassExW(&wc);

        let title = to_wide("RuneCore Marshal — Status");
        let hwnd = CreateWindowExW(
            0,
            class_name.as_ptr(),
            title.as_ptr(),
            WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX
                | WS_THICKFRAME | WS_VISIBLE,
            CW_USEDEFAULT, CW_USEDEFAULT,
            660, 500,
            ptr::null_mut(), ptr::null_mut(), hi, ptr::null_mut(),
        );

        if hwnd.is_null() {
            WINDOW_OPEN.store(false, Ordering::SeqCst);
            destroy_gdi_resources();
            return;
        }

        WINDOW_HWND.store(hwnd as usize, Ordering::SeqCst);
        ShowWindow(hwnd, SW_SHOW);
        UpdateWindow(hwnd);

        let mut msg: MSG = std::mem::zeroed();
        while GetMessageW(&mut msg, ptr::null_mut(), 0, 0) > 0 {
            TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
        // WM_DESTROY already cleared atomics and freed GDI resources
    });
}

// ── Entry point ───────────────────────────────────────────────────────────────

fn main() {
    let event_loop = EventLoopBuilder::<Status>::with_user_event()
        .build()
        .expect("event loop failed");

    let proxy = event_loop.create_proxy();

    let label_item = MenuItem::new("RuneCore Marshal", false, None);
    let quit_item  = MenuItem::new("Quit Tray",        true,  None);
    let quit_id    = quit_item.id().clone();

    let menu = Menu::new();
    menu.append(&label_item).unwrap();
    menu.append(&PredefinedMenuItem::separator()).unwrap();
    menu.append(&quit_item).unwrap();

    let tray = TrayIconBuilder::new()
        .with_menu(Box::new(menu))
        .with_tooltip(tooltip_text(Status::Unknown))
        .with_icon(make_icon(Status::Unknown))
        .build()
        .expect("failed to create tray icon");

    // Background thread: poll Marshal port, push icon/tooltip updates
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

        if let Event::UserEvent(status) = event {
            let _ = tray.set_icon(Some(make_icon(status)));
            let _ = tray.set_tooltip(Some(tooltip_text(status).to_string()));
        }

        if let Ok(e) = tray_rx.try_recv() {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = e {
                spawn_status_window();
            }
        }

        if let Ok(e) = menu_rx.try_recv() {
            if e.id == quit_id {
                elwt.exit();
            }
        }
    }).expect("event loop error");
}
