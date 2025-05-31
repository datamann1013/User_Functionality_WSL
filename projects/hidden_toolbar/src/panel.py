import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf

from utils import get_screen_size, run_command

class HiddenToolbar(Gtk.Window):
    def __init__(self):
        super().__init__()
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_keep_above(True)
        self.set_type_hint(Gdk.WindowTypeHint.DOCK)
        self.set_opacity(1.0)  # Always visible for testing

        # Set background color to match Windows taskbar
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            window {
                background-color: #2b2b2b;
                border-radius: 6px;
                padding: 4px;
            }
            button {
                background-color: transparent;
                border: none;
                padding: 2px;
            }
            image {
                margin: 0;
            }
        """)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Set window size
        window_width = 100
        window_height = 40
        self.set_size_request(window_width, window_height)

        # Position the window at the bottom center of the screen
        screen_width, screen_height = get_screen_size()
        x = Gtk.WindowPosition.CENTER #screen_width // 2
        y = window_height - screen_height -10  # 10px above bottom edge
        self.move(x, y)

        # Create a horizontal box centered in the window
        box = Gtk.Box(spacing=6)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        self.add(box)

        # Load and scale icons
        def load_icon(path, size=24):
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, size, size, True)
            return Gtk.Image.new_from_pixbuf(pixbuf)

        terminal_icon = load_icon("icons/terminal.png")
        filemanager_icon = load_icon("icons/folder.png")
        launcher_icon = load_icon("icons/search.png")

        # Terminal button
        terminal_button = Gtk.Button()
        terminal_button.set_image(terminal_icon)
        terminal_button.connect("clicked", lambda w: run_command("alacritty"))

        # File manager button
        filemanager_button = Gtk.Button()
        filemanager_button.set_image(filemanager_icon)
        filemanager_button.connect("clicked", lambda w: run_command("pcmanfm"))

        # App launcher button
        launcher_button = Gtk.Button()
        launcher_button.set_image(launcher_icon)
        launcher_button.connect("clicked", lambda w: run_command("rofi -show drun"))

        # Add buttons to box (no expansion)
        box.pack_start(terminal_button, False, False, 0)
        box.pack_start(filemanager_button, False, False, 0)
        box.pack_start(launcher_button, False, False, 0)

        self.connect("destroy", Gtk.main_quit)
        self.show_all()
