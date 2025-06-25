import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib

from utils import run_command
import os

class HiddenToolbar(Gtk.Window):
    def __init__(self):
        super().__init__()

        self.set_decorated(False)
        self.set_resizable(False)
        self.set_keep_above(True)
        self.set_opacity(1.0)
        self.set_title("hidden_toolbar")
        self.positioned = False

        self.window_width = 400
        self.window_height = 40
        self.set_default_size(self.window_width, self.window_height)
        # Try POPUP_MENU type hint to minimize border/shadow in VcXsrv
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

        def load_icon(filename, size=24):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            icon_path = os.path.join(base_dir, "icons", filename)
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(icon_path, size, size, True)
            return Gtk.Image.new_from_pixbuf(pixbuf)

        terminal_icon = load_icon("terminal.png")
        filemanager_icon = load_icon("folder.png")
        launcher_icon = load_icon("search.png")

        terminal_button = Gtk.Button()
        terminal_button.set_image(terminal_icon)
        terminal_button.connect("clicked", lambda w: run_command("xterm"))

        filemanager_button = Gtk.Button()
        filemanager_button.set_image(filemanager_icon)
        filemanager_button.connect("clicked", lambda w: run_command("pcmanfm"))

        launcher_button = Gtk.Button()
        launcher_button.set_image(launcher_icon)
        launcher_button.connect("clicked", lambda w: run_command("rofi -show drun"))

        inner_box.pack_start(terminal_button, False, False, 0)
        inner_box.pack_start(filemanager_button, False, False, 0)
        inner_box.pack_start(launcher_button, False, False, 0)

        outer_box.pack_start(inner_box, True, True, 0)

        self.connect("destroy", Gtk.main_quit)
        self.connect("realize", self.defer_positioning)
        self.show_all()

    def defer_positioning(self, widget):
        GLib.timeout_add(100, self.position_window)  # Delay by 100ms

    def position_window(self):
        if self.positioned:
             return False

        self.positioned = True

        screen = self.get_screen()
        monitor_index = screen.get_primary_monitor()
        geometry = screen.get_monitor_geometry(monitor_index)

        window_width = self.get_allocated_width()
        window_height = self.get_allocated_height()

        x = geometry.x + (geometry.width - window_width) // 2
        y = geometry.y + geometry.height - window_height

        print(
            f"[DEBUG] Monitor geometry: x={geometry.x}, y={geometry.y}, width={geometry.width}, height={geometry.height}")
        print(f"[DEBUG] Window size: width={window_width}, height={window_height}")
        print(f"[DEBUG] Moving window to: x={x}, y={y}")

        self.move(x, y)
        return False


if __name__ == "__main__":
    toolbar = HiddenToolbar()
    Gtk.main()
