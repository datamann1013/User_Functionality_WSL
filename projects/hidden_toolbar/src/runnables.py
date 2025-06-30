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
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.set_halign(Gtk.Align.FILL)
        self.set_valign(Gtk.Align.FILL)
        self.set_hexpand(True)
        self.set_vexpand(True)
        # Example content, replace with your actual runnables UI
        label = Gtk.Label(label="Runnables go here!")
        self.pack_start(label, True, True, 0)
