import gi
import logging

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

logging.basicConfig(level=logging.DEBUG)

class ProgramLauncher(Gtk.Window):
    def __init__(self, programs):
        super().__init__(title="Program Launcher")
        # Explicitly set a safe, fixed window size
        width, height = 800, 600
        # Safety check: never exceed 32767
        width = min(width, 32767)
        height = min(height, 32767)
        self.set_default_size(width, height)
        self.set_resizable(False)
        self.set_position(Gtk.WindowPosition.CENTER)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.add(vbox)
        self.listbox = Gtk.ListBox()
        for prog in programs:
            row = Gtk.ListBoxRow()
            label = Gtk.Label(label=prog, xalign=0)
            row.add(label)
            self.listbox.add(row)
        vbox.pack_start(self.listbox, True, True, 0)
        self.show_all()

def show_launcher(programs):
    logging.debug("Calling show_launcher")
    win = ProgramLauncher(programs)
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()
