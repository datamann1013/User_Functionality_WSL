import subprocess

def is_fullscreen():
    try:
        output = subprocess.check_output("xprop -root _NET_WM_STATE", shell=True).decode()
        return "_NET_WM_STATE_FULLSCREEN" in output
    except subprocess.CalledProcessError:
        return False
