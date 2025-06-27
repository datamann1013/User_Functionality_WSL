import gi
import os

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

class ProgramLauncher(Gtk.Window):
    def __init__(self, programs=None):
        super().__init__(title="Program Launcher")
        self.set_default_size(200, 60)
        # Use a box and a label, like in panel.py
        outer_box = Gtk.Box()
        outer_box.set_halign(Gtk.Align.FILL)
        outer_box.set_valign(Gtk.Align.FILL)
        outer_box.set_hexpand(True)
        outer_box.set_vexpand(True)
        self.add(outer_box)

        inner_box = Gtk.Box(spacing=6)
        inner_box.set_halign(Gtk.Align.CENTER)
        inner_box.set_valign(Gtk.Align.CENTER)

        label = Gtk.Label(label="Static text shown using the same method as icons.")
        inner_box.pack_start(label, False, False, 0)
        outer_box.pack_start(inner_box, True, True, 0)

        self.show_all()

def show_launcher(programs=None):
    win = ProgramLauncher(programs)
    Gtk.main()

if __name__ == "__main__":
    win = ProgramLauncher()
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()
