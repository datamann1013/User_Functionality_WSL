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
        self.runnables_open = False
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
        terminal_button.set_tooltip_text("Open Terminal")
        terminal_button.connect("clicked", lambda w: run_command("xterm"))

        filemanager_button = Gtk.Button()
        filemanager_button.set_image(filemanager_icon)
        filemanager_button.set_tooltip_text("Open File Manager")
        # Open Windows Explorer in the root of the current WSL distro
        def open_wsl_root(_):
            distro = os.environ.get("WSL_DISTRO_NAME")
            if distro:
                unc_path = f"\\\\wsl$\\{distro}\\"
                print(f"[DEBUG] Opening Windows Explorer at: {unc_path}")
                try:
                    subprocess.Popen(["explorer.exe", unc_path])
                except Exception as e:
                    print(f"[ERROR] Could not open explorer.exe: {e}")
            else:
                print("[ERROR] WSL_DISTRO_NAME not set. Opening current directory instead.")
                run_command("explorer.exe .")
        filemanager_button.connect("clicked", open_wsl_root)

        launcher_button = Gtk.Button()
        launcher_button.set_image(launcher_icon)
        launcher_button.set_tooltip_text("Open Program Launcher")
        # Launch the correct runnable (the minimal ProgramLauncher window)
        #launcher_button.connect("clicked", self.launch_runnables)

        # Add the runnables panel, initially hidden
        from runnables import RunnablesPanel
        self.runnables_panel = RunnablesPanel()
        self.runnables_panel.hide()
        outer_box.pack_start(self.runnables_panel, True, True, 0)

        inner_box.pack_start(terminal_button, False, False, 0)
        inner_box.pack_start(filemanager_button, False, False, 0)
        inner_box.pack_start(launcher_button, False, False, 0)

        outer_box.pack_start(inner_box, True, True, 0)

        self.connect("destroy", Gtk.main_quit)
        self.connect("realize", self.defer_positioning)
        self.show_all()

        def toggle_runnables_panel(widget):
            if self.runnables_panel.get_visible():
                self.runnables_panel.hide()
                self.set_default_size(self.window_width, 40)
                self.runnables_open = False
            else:
                self.runnables_panel.show_all()
                self.set_default_size(self.window_width, 600)
                self.runnables_open = True
        launcher_button.connect("clicked", toggle_runnables_panel)

    def defer_positioning(self, widget):
        # Increase delay to 300ms to ensure window is fully realized before moving
        GLib.timeout_add(300, self.position_window)  # Delay by 300ms

    def position_window(self):
        if self.positioned:
             return False

        self.positioned = True

        screen = self.get_screen()
        monitor_index = screen.get_primary_monitor()
        geometry = screen.get_monitor_geometry(monitor_index)

        window_width = self.get_allocated_width()
        window_height = self.get_allocated_height()

        # Move the window a bit higher to sit above the taskbar (e.g., 10px)
        offset = 46
        x = geometry.x + (geometry.width - window_width) // 2
        y = geometry.y + geometry.height - window_height - offset

        print(
            f"[DEBUG] Monitor geometry: x={geometry.x}, y={geometry.y}, width={geometry.width}, height={geometry.height}")
        print(f"[DEBUG] Window size: width={window_width}, height={window_height}")
        print(f"[DEBUG] Moving window to: x={x}, y={y}")

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
