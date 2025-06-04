import os
import sys
import gi
from panel import HiddenToolbar
from gi.repository import Gtk, Gdk

# Check DISPLAY environment variable
DISPLAY = os.environ.get('DISPLAY')
if not DISPLAY:
    print("[ERROR] DISPLAY environment variable is not set. Please ensure VcXsrv is running and DISPLAY is configured.")
    sys.exit(1)

# Check X server vendor
try:
    display = Gdk.Display.get_default()
    if display is None:
        raise RuntimeError("No X display found.")
    vendor = display.get_name() if hasattr(display, 'get_name') else str(display)
    # Try to get vendor string from Xlib if possible
    # Fallback: use Xlib directly if available
    try:
        import Xlib.display
        xdisp = Xlib.display.Display()
        vendor = xdisp.get_vendor()
    except Exception:
        pass
    print(f"[DEBUG] DISPLAY={DISPLAY}")
    print(f"[DEBUG] X server vendor: {vendor}")
    if 'VcXsrv' not in vendor:
        print("[ERROR] X server is not VcXsrv. Please start VcXsrv and set DISPLAY accordingly.")
        sys.exit(1)
except Exception as e:
    print(f"[ERROR] Could not determine X server vendor: {e}")
    sys.exit(1)

def main():
    win = HiddenToolbar()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()

if __name__ == "__main__":
    main()
