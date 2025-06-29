# main.py is now deprecated. All launching should be done via launcher.py

import os
import sys
import gi
from panel import HiddenToolbar
from gi.repository import Gtk, Gdk

import subprocess

def find_vcxsrv_display():
    # Try to find a running VcXsrv process and guess the DISPLAY
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if 'VcXsrv' in line:
                # Default VcXsrv display is :0.0, but could be different
                # Try to extract display number from command line
                if '-multiwindow' in line or '-fullscreen' in line or '-rootless' in line:
                    # Heuristic: use :0.0 if not specified
                    return ':0.0'
                import re
                m = re.search(r'-ac\s+-multiwindow\s+-screen\s+\d+\s+:(\d+)', line)
                if m:
                    return f':{m.group(1)}.0'
        return None
    except Exception:
        return None

DISPLAY = os.environ.get('DISPLAY')
if not DISPLAY or DISPLAY == ':0':
    guessed = find_vcxsrv_display()
    if guessed:
        os.environ['DISPLAY'] = guessed
        DISPLAY = guessed
        print(f"[INFO] DISPLAY not set or default, guessing VcXsrv display: {DISPLAY}")
    else:
        print("[ERROR] DISPLAY environment variable is not set and VcXsrv was not found running. Please start VcXsrv and set DISPLAY.")
        sys.exit(1)

# Only check DISPLAY is set, do not enforce vendor string
try:
    display = Gdk.Display.get_default()
    if display is None:
        raise RuntimeError("No X display found.")
    print(f"[DEBUG] DISPLAY={DISPLAY}")
    # Try to print vendor string if possible, but do not enforce
    try:
        import Xlib.display
        xdisp = Xlib.display.Display()
        vendor = xdisp.get_vendor()
        print(f"[DEBUG] X server vendor: {vendor}")
    except Exception:
        print("[DEBUG] X server vendor: (could not determine, but proceeding)")
except Exception as e:
    print(f"[ERROR] Could not connect to X server: {e}")
    sys.exit(1)

def main():
    try:
        win = HiddenToolbar()
        win.connect("destroy", Gtk.main_quit)
        win.show_all()
        Gtk.main()
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
