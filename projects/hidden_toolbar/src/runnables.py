import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib

class ProgramLauncher(Gtk.Window):
    def __init__(self, programs=None):
        super().__init__()
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_keep_above(True)
        self.set_opacity(1.0)
        self.set_title("hidden_toolbar_runnables")
        self.window_width = 400
        self.window_height = 40
        self.set_default_size(self.window_width, self.window_height)
        self.set_type_hint(Gdk.WindowTypeHint.POPUP_MENU)
        self.set_app_paintable(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)

        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            window {
                background-color: #2b2b2b;
                border-radius: 6px;
                border-width: 0;
                border: none;
                box-shadow: none;
            }
            button {
                background-color: transparent;
                border: none;
                border-width: 0;
                box-shadow: none;
                padding: 2px;
            }
        """)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        outer_box = Gtk.Box()
        outer_box.set_halign(Gtk.Align.FILL)
        outer_box.set_valign(Gtk.Align.FILL)
        outer_box.set_hexpand(True)
        outer_box.set_vexpand(True)
        self.add(outer_box)

        inner_box = Gtk.Box(spacing=6)
        inner_box.set_halign(Gtk.Align.CENTER)
        inner_box.set_valign(Gtk.Align.CENTER)

        label = Gtk.Label(label="This is a test label in the runnables window.")
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
