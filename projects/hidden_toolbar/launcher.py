import os
import sys
from src.panel import HiddenToolbar
from gi.repository import Gtk

def main():
    win = HiddenToolbar()
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()

if __name__ == "__main__" or __name__ == "projects.hidden_toolbar.launcher":
    main()
