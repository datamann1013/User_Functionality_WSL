import subprocess
from gi.repository import Gdk

def get_screen_size():
    screen = Gdk.Screen.get_default()
    return screen.get_width(), screen.get_height()

def run_command(command):
    import os
    env = os.environ.copy()
    subprocess.Popen(command, shell=True, env=env)

