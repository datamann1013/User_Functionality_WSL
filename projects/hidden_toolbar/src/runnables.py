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
import json
import random

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
        self.window_height = 600
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

        outer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer_box.set_halign(Gtk.Align.FILL)
        outer_box.set_valign(Gtk.Align.FILL)
        outer_box.set_hexpand(True)
        outer_box.set_vexpand(True)
        self.add(outer_box)

        inner_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        inner_box.set_halign(Gtk.Align.CENTER)
        inner_box.set_valign(Gtk.Align.CENTER)

        # Load scanned programs and create a button for each
        scanned_path = os.path.join(os.path.dirname(__file__), "scanned_programs.json")
        program_buttons = []
        if os.path.exists(scanned_path):
            with open(scanned_path, "r", encoding="utf-8") as f:
                programs = list(json.load(f).items())
                def make_image_button(prog_tuple):
                    from PIL import Image, ImageDraw, ImageFont
                    import io
                    width, height = 200, 32
                    img = Image.new('RGBA', (width, height), (255, 255, 255, 0))
                    d = ImageDraw.Draw(img)
                    try:
                        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 22)
                    except Exception:
                        try:
                            font = ImageFont.truetype("arial.ttf", 22)
                        except Exception:
                            font = ImageFont.load_default()
                    text = prog_tuple[0]
                    bbox = d.textbbox((0, 0), text, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    x = (width - text_width) // 2
                    y = (height - text_height) // 2
                    d.text((x, y), text, fill=(0, 0, 0, 255), font=font, anchor="lt")
                    buf = io.BytesIO()
                    img.save(buf, format='PNG')
                    buf.seek(0)
                    loader = GdkPixbuf.PixbufLoader.new_with_type('png')
                    loader.write(buf.read())
                    loader.close()
                    pixbuf = loader.get_pixbuf()
                    image = Gtk.Image.new_from_pixbuf(pixbuf)
                    btn = Gtk.Button()
                    btn.set_image(image)
                    btn.connect("clicked", lambda w: self.show_program_dialog(prog_tuple[0], prog_tuple[1]))
                    return btn
                program_buttons = [make_image_button(prog) for prog in programs]
        # Calculate menu height based on number of programs
        spacing = 12
        button_height = 32
        n = len(program_buttons)
        min_height = 120
        max_height = 600
        if n > 0:
            menu_height = spacing + n * (button_height + spacing)
            menu_height = max(min_height, min(menu_height, max_height))
            self.window_height = menu_height
            self.set_default_size(self.window_width, self.window_height)
        # Clear inner_box and add program buttons with spacing
        for btn in program_buttons:
            inner_box.pack_start(btn, False, False, spacing)
        # Add spacing to top and bottom
        inner_box.set_spacing(spacing)
        inner_box.set_margin_top(spacing)
        inner_box.set_margin_bottom(spacing)
        inner_box.set_margin_start(spacing)
        inner_box.set_margin_end(spacing)

        outer_box.pack_start(inner_box, True, True, 0)

        self.connect("destroy", Gtk.main_quit)
        self.connect("realize", self.defer_positioning)
        self.show_all()

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
        panel_height = 40
        offset = 46
        x = geometry.x + (geometry.width - window_width) // 2
        y = geometry.y + geometry.height - window_height - offset - panel_height

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

    def show_program_dialog(self, name, path):
        print(f"[PROGRAM INFO] {name}: {path}")
        # Optionally, you can also use notify-send or another mechanism if you want a desktop notification
        # import subprocess
        # subprocess.Popen(["notify-send", f"{name}", f"{path}"])


if __name__ == "__main__":
    toolbar = HiddenToolbar()
    Gtk.main()


