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

class RunnablesPanel(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_halign(Gtk.Align.FILL)
        self.set_valign(Gtk.Align.FILL)
        self.set_hexpand(True)
        self.set_vexpand(True)
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b'''
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
        ''')
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        inner_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        inner_box.set_halign(Gtk.Align.CENTER)
        inner_box.set_valign(Gtk.Align.CENTER)
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
        spacing = 12
        button_height = 32
        n = len(program_buttons)
        min_height = 120
        max_height = 600
        if n > 0:
            menu_height = spacing + n * (button_height + spacing)
            menu_height = max(min_height, min(menu_height, max_height))
            # Optionally, you can set a fixed height for the panel if needed
        for btn in program_buttons:
            inner_box.pack_start(btn, False, False, spacing)
        inner_box.set_spacing(spacing)
        inner_box.set_margin_top(spacing)
        inner_box.set_margin_bottom(spacing)
        inner_box.set_margin_start(spacing)
        inner_box.set_margin_end(spacing)
        self.pack_start(inner_box, True, True, 0)
    def show_program_dialog(self, name, path):
        print(f"[PROGRAM INFO] {name}: {path}")
