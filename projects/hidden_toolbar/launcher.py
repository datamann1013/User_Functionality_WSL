import os
import sys

if __name__ == "__main__":
    print("Please run this launcher using: python3 -m projects.hidden_toolbar.launcher")
    sys.exit(1)

from .src.runnables import show_launcher

def get_linux_runnables():
    paths = os.environ.get("PATH", "").split(os.pathsep)
    seen = set()
    programs = []
    for path in paths:
        if not os.path.isdir(path):
            continue
        for fname in os.listdir(path):
            fpath = os.path.join(path, fname)
            if fname in seen:
                continue
            if os.path.isfile(fpath) and os.access(fpath, os.X_OK):
                # Filter out python files in this project
                if fname.endswith(".py") and os.path.dirname(fpath) == os.path.abspath(os.path.dirname(__file__)):
                    continue
                # Exclude Windows .exe apps
                if fname.lower().endswith('.exe'):
                    continue
                seen.add(fname)
                programs.append(fname)
    programs = sorted(set(programs), key=lambda x: x.lower())
    return programs

def main():
    programs = get_linux_runnables()
    show_launcher(programs)

if __name__ == "__main__":
    main()
