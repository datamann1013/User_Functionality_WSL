import gi
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk
import subprocess
import json
import os
import threading

USAGE_FILE = os.path.join(os.path.dirname(__file__), '..', 'program_usage.json')

def get_screen_size():
    screen = Gdk.Screen.get_default()
    return screen.get_width(), screen.get_height()

def run_command(command):
    env = os.environ.copy()
    subprocess.Popen(command, shell=True, env=env)

def load_usage_data():
    try:
        with open(USAGE_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {'last_used': [], 'favourites': []}

def save_usage_data(data):
    try:
        with open(USAGE_FILE, 'w') as f:
            json.dump(data, f)
    except Exception:
        pass

def add_last_used(program):
    data = load_usage_data()
    if program in data['last_used']:
        data['last_used'].remove(program)
    data['last_used'].insert(0, program)
    data['last_used'] = data['last_used'][:5]
    save_usage_data(data)

def toggle_favourite(program):
    data = load_usage_data()
    if program in data['favourites']:
        data['favourites'].remove(program)
    else:
        data['favourites'].insert(0, program)
        data['favourites'] = data['favourites'][:5]
    save_usage_data(data)

def is_favourite(program):
    data = load_usage_data()
    return program in data['favourites']

def scan_development_programs():
    """
    Scan for common development programs in PATH and cache the result.
    """
    import shutil
    dev_programs = [
        # IDEs
        "code", "pycharm", "eclipse", "idea", "clion", "netbeans", "geany",
        # Editors
        "vim", "emacs", "gedit", "kate", "sublime_text", "atom", "nano",
        # Terminals
        "gnome-terminal", "konsole", "xterm", "tilix", "alacritty", "terminator",
        # Others
        "thunderbird", "dbeaver", "mysql-workbench", "android-studio"
    ]
    found = {}
    for prog in dev_programs:
        path = shutil.which(prog)
        print(f"[DEBUG] Scanning: {prog} -> {path}")
        if path and os.path.exists(path):
            # Exclude Windows executables mounted via /mnt/*
            if path.startswith("/mnt/") and len(path) > 6 and path[5].isalpha() and path[6] == '/':
                print(f"[DEBUG] Skipping {prog} (Windows binary detected: {path})")
                continue
            # Only add if the binary is actually present in the current distro
            found[prog] = path
    cache_path = os.path.join(os.path.dirname(__file__), "scanned_programs.json")
    try:
        with open(cache_path, "w") as f:
            json.dump(found, f)
        print(f"[DEBUG] Wrote {len(found)} programs to {cache_path}")
        print(f"[DEBUG] JSON: {json.dumps(found, indent=2)}")
    except Exception as e:
        print(f"[DEBUG] Failed to write scanned_programs.json: {e}")

def scan_development_programs_background():
    threading.Thread(target=scan_development_programs, daemon=True).start()
