#!/usr/bin/env python3
from .src.panel import HiddenToolbar
from .src.utils import scan_development_programs_background, ensure_x_server
from gi.repository import Gtk
import os

def main():
    print(f"[DEBUG] DISPLAY={os.environ.get('DISPLAY')}")
    ensure_x_server()
    scan_development_programs_background()
    success, _ = Gtk.init_check()
    if not success:
        print("Error: Gtk couldn't be initialized. Make sure you have a valid DISPLAY and X server running.")
        exit(1)
    win = HiddenToolbar()
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()

if __name__ == "__main__":
    main()
