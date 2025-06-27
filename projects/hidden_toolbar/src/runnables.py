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
        # Load scanned_programs.json and extract the first program name
        scanned_path = os.path.join(os.path.dirname(__file__), "scanned_programs.json")
        first_program = "No program found"
        if os.path.exists(scanned_path):
            with open(scanned_path, "r") as f:
                try:
                    data = json.load(f)
                    if data:
                        first_program = next(iter(data.keys()))
                except Exception:
                    pass
        label = Gtk.Label(label=first_program)
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
