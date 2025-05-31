import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GdkPixbuf

from utils import get_screen_size, run_command

class HiddenToolbar(Gtk.Window):
    def __init__(self):
        super().__init__()

        # Basic window setup
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_keep_above(True)
        self.set_opacity(1.0)

        # Set a wider window to allow true centering
        self.window_width = 400  # Increased width
        self.window_height = 40
        self.set_default_size(self.window_width, self.window_height)

        # Apply minimal styling
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            window {
                background-color: #2b2b2b;
                border-radius: 6px;
            }
            button {
                background-color: transparent;
                border: none;
                padding: 2px;
            }
        """)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Outer box fills the window
        outer_box = Gtk.Box()
        outer_box.set_halign(Gtk.Align.FILL)
        outer_box.set_valign(Gtk.Align.FILL)
        outer_box.set_hexpand(True)
        outer_box.set_vexpand(True)
        self.add(outer_box)

        # Inner box is centered
        inner_box = Gtk.Box(spacing=6)
        inner_box.set_halign(Gtk.Align.CENTER)
        inner_box.set_valign(Gtk.Align.CENTER)

        # Load and scale icons
        def load_icon(path, size=24):
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, size, size, True)
            return Gtk.Image.new_from_pixbuf(pixbuf)

        terminal_icon = load_icon("icons/terminal.png")
        filemanager_icon = load_icon("icons/folder.png")
        launcher_icon = load_icon("icons/search.png")

        # Create buttons
        terminal_button = Gtk.Button()
        terminal_button.set_image(terminal_icon)
        terminal_button.connect("clicked", lambda w: run_command("alacritty"))

        filemanager_button = Gtk.Button()
        filemanager_button.set_image(filemanager_icon)
        filemanager_button.connect("clicked", lambda w: run_command("pcmanfm"))

        launcher_button = Gtk.Button()
        launcher_button.set_image(launcher_icon)
        launcher_button.connect("clicked", lambda w: run_command("rofi -show drun"))

        # Add buttons to inner box
        inner_box.pack_start(terminal_button, False, False, 0)
        inner_box.pack_start(filemanager_button, False, False, 0)
        inner_box.pack_start(launcher_button, False, False, 0)

        # Add inner box to outer box
        outer_box.pack_start(inner_box, True, True, 0)

        self.connect("destroy", Gtk.main_quit)
        self.connect("realize", self.on_realize)
        self.show_all()

    def on_realize(self, widget):
        screen_width, screen_height = get_screen_size()
        panel_height = -5  # Adjust this to match your tint2 or taskbar height
        x = (screen_width - self.window_width) // 2
        y = screen_height - self.window_height - panel_height
        self.move(x, y)


if __name__ == "__main__":
    toolbar = HiddenToolbar()
    Gtk.main()
