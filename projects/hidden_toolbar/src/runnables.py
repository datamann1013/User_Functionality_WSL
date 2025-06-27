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
        # Load and display the scanned_programs.json as raw JSON
        scanned_path = os.path.join(os.path.dirname(__file__), "scanned_programs.json")
        if os.path.exists(scanned_path):
            with open(scanned_path, "r") as f:
                json_content = f.read()
        else:
            json_content = "{}"
        label = Gtk.Label(label=json_content)
        self.add(label)
        self.show_all()

def show_launcher(programs=None):
    win = ProgramLauncher(programs)
    Gtk.main()

if __name__ == "__main__":
    from gi.repository import Gtk
    win = ProgramLauncher()
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()
