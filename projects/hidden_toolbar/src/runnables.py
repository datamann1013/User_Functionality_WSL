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
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_halign(Gtk.Align.FILL)
        self.set_valign(Gtk.Align.FILL)
        self.set_hexpand(True)
        self.set_vexpand(True)
        # Copy the original window's style and layout
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b'''
            window, box {
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
        # Main content area
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.content_box.set_halign(Gtk.Align.FILL)
        self.content_box.set_valign(Gtk.Align.FILL)
        self.content_box.set_hexpand(True)
        self.content_box.set_vexpand(True)
        # Example: Add a label and a close button
        label = Gtk.Label(label="Runnables go here!")
        label.set_margin_top(12)
        label.set_margin_bottom(12)
        label.set_margin_start(12)
        label.set_margin_end(12)
        close_btn = Gtk.Button(label="Close")
        close_btn.set_halign(Gtk.Align.END)
        close_btn.connect("clicked", lambda w: self.hide())
        self.content_box.pack_start(label, False, False, 0)
        self.content_box.pack_start(close_btn, False, False, 0)
        self.pack_start(self.content_box, True, True, 0)
