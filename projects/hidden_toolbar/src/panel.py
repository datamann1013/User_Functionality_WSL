import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib

from utils import get_screen_size, run_command
from visibility import is_fullscreen

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

        width, height = get_screen_size()
        self.set_size_request(60, 20)  # Small bump size
        self.move((width - 60) // 2, height - 40)  # Just above Windows taskbar

        box = Gtk.Box(spacing=4)
        self.add(box)

        # Load icons
        terminal_icon = Gtk.Image.new_from_file("icons/terminal.png")
        filemanager_icon = Gtk.Image.new_from_file("icons/filemanager.png")
        launcher_icon = Gtk.Image.new_from_file("icons/launcher.png")

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

        # Add buttons to box
        box.pack_start(terminal_button, True, True, 0)
        box.pack_start(filemanager_button, True, True, 0)
        box.pack_start(launcher_button, True, True, 0)

        self.connect("destroy", Gtk.main_quit)
        self.show_all()
