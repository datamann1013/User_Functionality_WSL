import gi
import os
import json

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

class ProgramLauncher(Gtk.Window):
    def __init__(self, programs=None):
        try:
            print("[DEBUG] ProgramLauncher __init__ start")
            print(f"[DEBUG] Current working directory: {os.getcwd()}")
            super().__init__(title="Program Launcher")
            print("[DEBUG] Gtk.Window initialized")
            self.set_default_size(800, 600)
            print("[DEBUG] set_default_size called")
            self.connect("destroy", Gtk.main_quit)
            print("[DEBUG] destroy signal connected")
            scanned_path = os.path.join(os.path.dirname(__file__), "scanned_programs.json")
            print(f"[DEBUG] scanned_path: {scanned_path}")
            print(f"[DEBUG] scanned_programs.json exists: {os.path.exists(scanned_path)}")
            first_program = "No program found"
            if os.path.exists(scanned_path):
                print("[DEBUG] scanned_programs.json exists")
                with open(scanned_path, "r") as f:
                    try:
                        data = json.load(f)
                        print(f"[DEBUG] loaded json: {data}")
                        if data:
                            first_program = next(iter(data.keys()))
                            print(f"[DEBUG] first_program: {first_program}")
                    except Exception as e:
                        print(f"[DEBUG] Exception loading json: {e}")
            else:
                print("[DEBUG] scanned_programs.json does not exist")
            print(f"[DEBUG] About to create Gtk.Label with: {first_program}")
            label = Gtk.Label(label=first_program)
            print("[DEBUG] Gtk.Label created")
            self.add(label)
            print("[DEBUG] label added to window")
            self.show_all()
            print("[DEBUG] show_all called")
        except Exception as e:
            print(f"[DEBUG] Exception in ProgramLauncher __init__: {e}")

def show_launcher(programs=None):
    win = ProgramLauncher(programs)
    Gtk.main()

if __name__ == "__main__":
    from gi.repository import Gtk
    win = ProgramLauncher()
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()
