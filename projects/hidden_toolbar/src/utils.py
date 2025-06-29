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
    import shutil
    dev_programs = [
        "code", "pycharm", "eclipse", "idea", "clion", "netbeans", "geany",
        "vim", "emacs", "gedit", "kate", "sublime_text", "atom", "nano",
        "gnome-terminal", "konsole", "xterm", "tilix", "alacritty", "terminator",
        "thunderbird", "dbeaver", "mysql-workbench", "android-studio"
    ]
    found = {}
    for prog in dev_programs:
        path = shutil.which(prog)
        if path and os.path.exists(path):
            if path.startswith("/mnt/") and len(path) > 6 and path[5].isalpha() and path[6] == '/':
                continue
            found[prog] = path
    cache_path = os.path.join(os.path.dirname(__file__), "scanned_programs.json")
    try:
        with open(cache_path, "w") as f:
            json.dump(found, f)
    except Exception:
        pass

def scan_development_programs_background():
    threading.Thread(target=scan_development_programs, daemon=True).start()

def find_vcxsrv_display():
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if 'VcXsrv' in line:
                if '-multiwindow' in line or '-fullscreen' in line or '-rootless' in line:
                    return ':0.0'
                import re
                m = re.search(r'-ac\s+-multiwindow\s+-screen\s+\d+\s+:(\d+)', line)
                if m:
                    return f':{m.group(1)}.0'
        return None
    except Exception:
        return None

def ensure_x_server():
    DISPLAY = os.environ.get('DISPLAY')
    if not DISPLAY or DISPLAY == ':0':
        guessed = find_vcxsrv_display()
        if guessed:
            os.environ['DISPLAY'] = guessed
            DISPLAY = guessed
        else:
            print("[ERROR] DISPLAY environment variable is not set and VcXsrv was not found running. Please start VcXsrv and set DISPLAY.")
            exit(1)
    try:
        display = Gdk.Display.get_default()
        if display is None:
            raise RuntimeError("No X display found.")
        try:
            import Xlib.display
            xdisp = Xlib.display.Display()
            xdisp.get_vendor()
        except Exception:
            pass
    except Exception as e:
        print(f"[ERROR] Could not connect to X server: {e}")
        exit(1)
