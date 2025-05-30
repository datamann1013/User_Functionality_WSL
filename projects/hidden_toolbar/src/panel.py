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
        self.set_opacity(0.0)

        width, height = get_screen_size()
        self.set_size_request(50, 10)
        self.move((width - 50) // 2, height - 30)

        box = Gtk.Box(spacing=6)
        self.add(box)

        terminal_icon = Gtk.Image.new_from_file("icons/terminal.png")
        filemanager_icon = Gtk.Image.new_from_file("icons/filemanager.png")
        launcher_icon = Gtk.Image.new_from_file("icons/launcher.png")

        terminal_button = Gtk.Button()
        terminal_button.set_image(terminal_icon)
        terminal_button.connect("clicked", lambda w: run_command("alacritty"))

        filemanager_button = Gtk.Button()
        filemanager_button.set_image(filemanager_icon)
        filemanager_button.connect("clicked", lambda w: run_command("pcmanfm"))

        launcher_button = Gtk.Button()
        launcher_button.set_image(launcher_icon)
        launcher_button.connect("clicked", lambda w: run_command("rofi -show drun"))

        box.pack_start(terminal_button, True, True, 0)
        box.pack_start(filemanager_button, True, True, 0)
        box.pack_start(launcher_button, True, True, 0)

        self.connect("enter-notify-event", self.on_mouse_enter)
        self.connect("leave-notify-event", self.on_mouse_leave)

        GLib.timeout_add(1000, self.check_fullscreen)

    def on_mouse_enter(self, widget, event):
        self.set_opacity(1.0)

    def on_mouse_leave(self, widget, event):
        self.set_opacity(0.0)

    def check_fullscreen(self):
        if is_fullscreen():
            self.set_opacity(0.0)
        return True
