import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib

from utils import run_command
import subprocess
import threading
import traceback

class HiddenToolbar(Gtk.Window):
    def __init__(self):

        self.set_decorated(False)
        self.set_resizable(False)
        self.set_keep_above(True)
        self.set_opacity(1.0)
        self.set_title("hidden_toolbar")
        self.positioned = False

        self.window_width = 500
        self.window_height = 120
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
                background-color: #444;
                color: #fff;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                margin: 4px;
                font-size: 14px;
            }
            button:hover {
                background-color: #666;
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

        inner_box = Gtk.Box(spacing=16)
        inner_box.set_halign(Gtk.Align.CENTER)
        inner_box.set_valign(Gtk.Align.CENTER)

        terminal_button = Gtk.Button(label="Terminal")
        terminal_button.connect("clicked", lambda w: run_command("xterm"))

        filemanager_button = Gtk.Button(label="File Manager")
        filemanager_button.connect("clicked", lambda w: run_command("explorer.exe ~"))

        launcher_button = Gtk.Button(label="Launcher")
        launcher_button.connect("clicked", self.launch_runnables)

        inner_box.pack_start(terminal_button, False, False, 0)
        inner_box.pack_start(filemanager_button, False, False, 0)
        inner_box.pack_start(launcher_button, False, False, 0)

        outer_box.pack_start(inner_box, True, True, 0)

        self.connect("destroy", Gtk.main_quit)
        self.connect("realize", self.defer_positioning)
        self.show_all()

    def defer_positioning(self, widget):
        # Position this window just above the panel (not covering it)
        GLib.timeout_add(300, self.position_window)

    def position_window(self):
        if self.positioned:
            return False
        self.positioned = True
        screen = self.get_screen()
        monitor_index = screen.get_primary_monitor()
        geometry = screen.get_monitor_geometry(monitor_index)
        window_width = self.get_allocated_width()
        window_height = self.get_allocated_height()
        # Place this window just above where the panel sits (assume panel is at bottom)
        panel_height = 40  # match panel height
        offset = 46
        x = geometry.x + (geometry.width - window_width) // 2
        y = geometry.y + geometry.height - window_height - panel_height - offset
        self.move(x, y)
        return False

    def launch_runnables(self, widget):
        def run_runnables():
            try:
                runnables_path = os.path.join(os.path.dirname(__file__), "runnables.py")
                print(f"[DEBUG] Launching runnables: python3 {runnables_path}")
                proc = subprocess.Popen([
                    sys.executable, runnables_path
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=os.path.dirname(__file__))
                stdout, stderr = proc.communicate()
                if proc.returncode != 0 or stderr:
                    error_msg = f"Runnables exited with code {proc.returncode}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
                    print(error_msg)
                    GLib.idle_add(self.show_error_dialog, error_msg)
            except Exception as e:
                import traceback
                err = f"Failed to launch runnables: {e}\n{traceback.format_exc()}"
                print(err)
                GLib.idle_add(self.show_error_dialog, err)
        threading.Thread(target=run_runnables, daemon=True).start()

    def show_error_dialog(self, message):
        dialog = Gtk.MessageDialog(self, 0, Gtk.MessageType.ERROR, Gtk.ButtonsType.OK, f"Launcher error:\n{message}")
        dialog.run()
        dialog.destroy()


if __name__ == "__main__":
    toolbar = HiddenToolbar()
    Gtk.main()
