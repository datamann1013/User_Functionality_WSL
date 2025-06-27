import subprocess
from gi.repository import Gdk
import json
import os

USAGE_FILE = os.path.join(os.path.dirname(__file__), '..', 'program_usage.json')

def get_screen_size():
    screen = Gdk.Screen.get_default()
    return screen.get_width(), screen.get_height()

def run_command(command):
    import os
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
