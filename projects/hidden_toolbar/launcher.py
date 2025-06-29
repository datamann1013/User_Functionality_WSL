#!/usr/bin/env python3
import sys
from .src.panel import HiddenToolbar
from .src.utils import scan_development_programs_background
from gi.repository import Gtk

def main():
    scan_development_programs_background()
    success, _ = Gtk.init_check()
    if not success:
        print("Error: Gtk couldn't be initialized. Make sure you have a valid DISPLAY and X server running.")
        sys.exit(1)
    win = HiddenToolbar()
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()

if __name__ == "__main__":
    main()
