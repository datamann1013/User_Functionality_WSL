import gi
import os
import json

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

class ProgramLauncher(Gtk.Window):
    def __init__(self, programs=None):
        super().__init__(title="Program Launcher")
        self.set_default_size(800, 600)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(vbox)
        # Load scanned programs
        scanned_path = os.path.join(os.path.dirname(__file__), "scanned_programs.json")
        programs_list = []
        if os.path.exists(scanned_path):
            with open(scanned_path, "r") as f:
                data = json.load(f)
                programs_list = list(data.keys())[:10]
        else:
            programs_list = ["No scanned_programs.json found"]
        # Display first 10 programs
        for prog in programs_list:
            label = Gtk.Label(label=prog)
            vbox.pack_start(label, False, False, 0)
        self.show_all()

def show_launcher(programs=None):
    win = ProgramLauncher(programs)
    Gtk.main()

if __name__ == "__main__":
    from gi.repository import Gtk
    win = ProgramLauncher()
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()
