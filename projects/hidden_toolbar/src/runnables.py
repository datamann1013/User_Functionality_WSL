import gi
import os
import json

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

class ProgramLauncher(Gtk.Window):
    def __init__(self, programs=None):
        super().__init__(title="Program Launcher")
        self.set_default_size(400, 100)
        self.connect("destroy", Gtk.main_quit)
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
        label.set_margin_top(20)
        label.set_margin_bottom(20)
        label.set_margin_start(20)
        label.set_margin_end(20)
        label.set_justify(Gtk.Justification.CENTER)
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
