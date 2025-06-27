import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

class ProgramLauncher(Gtk.Window):
    def __init__(self, programs=None):
        super().__init__(title="Program Launcher")
        self.set_default_size(200, 60)

        label = Gtk.Label(label="Test text")
        self.add(label)
        self.show_all()

def show_launcher(programs=None):
    win = ProgramLauncher(programs)
    Gtk.main()

if __name__ == "__main__":
    win = ProgramLauncher()
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()
