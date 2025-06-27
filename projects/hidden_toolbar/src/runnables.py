import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

class ProgramLauncher(Gtk.Window):
    def __init__(self, programs):
        super().__init__(title="Program Launcher")
        self.set_default_size(800, 600)
        self.show_all()

def show_launcher(programs):
    win = ProgramLauncher(programs)
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()
