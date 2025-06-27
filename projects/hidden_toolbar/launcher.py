import os
import sys
from .src.panel import HiddenToolbar
from .src.utils import scan_development_programs_background
from gi.repository import Gtk

def main():
    scan_development_programs_background()
    win = HiddenToolbar()
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()

if __name__ == "__main__":
    main()
