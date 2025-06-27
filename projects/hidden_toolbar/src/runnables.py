import gi
import os
import json

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

class ProgramLauncher(Gtk.Window):
    def __init__(self, programs=None):
        super().__init__(title="Program Launcher")
        self.set_default_size(800, 600)
        self.connect("destroy", Gtk.main_quit)
        self.show_all()

def show_launcher(programs=None):
    win = ProgramLauncher(programs)
    Gtk.main()

if __name__ == "__main__":
    from gi.repository import Gtk
    win = ProgramLauncher()
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()
