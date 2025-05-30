# 🪟 Hidden Toolbar (Bump Launcher)

A discreet, hover-activated toolbar for WSL2 + Arch Linux + Openbox. 
Designed to give quick access to essential tools without cluttering the desktop.

---

## 🎯 Features

- Appears as a **small bump** at the **bottom center** of the screen
- **Invisible** when not hovered or when a window is fullscreen
- **Instantly appears** on hover
- Contains 3 icons:
  - 🖥️ Terminal (`alacritty` or `xterm`)
  - 📁 File Manager (`pcmanfm`)
  - 🔍 App Launcher (`rofi -show drun`)
- Works only on the **primary monitor**

---

## 🛠️ How It Works

- Built with **Python + GTK** for GUI
- Uses `xdotool` or `xprop` to detect fullscreen windows
- Uses `picom` for transparency (optional)
- Hover detection is handled via GTK events

---

## 📦 Requirements

Install dependencies:

---
sudo pacman -S python-gobject xdotool xprop wmctrl picom
pip install -r requirements.txt
---

---

## 🔐 Security Considerations

- Avoid running as root
- Only use trusted icons and scripts
- Avoid embedding sensitive commands

---

## 🧩 Future Ideas

- Add animation on hover
- Support for multiple monitors
- Configurable icon set

---
## 🚀 How to use:

### 0. (Optional) Reset WSL2
If you want to start fresh with a clean Linux environment:
- wsl --unregister archlinux
### 1. Install a Linux Distro in WSL2
You can install a distro from the Microsoft Store (e.g., Ubuntu, Debian, Arch).
For Arch, use a community installer like ArchWSL.
You can also use **wsl --install archlinux** for automated installation.
Once installed update the system with 
- sudo pacman -Syu
### 2. Install Required Packages
Install the following packages inside your WSL2 distro: 
- sudo pacman -S python python-gobject gtk3 xdotool xorg-xprop wmctrl picom rofi pcmanfm alacritty
### 3. Set Up X11 Display
Install and run VcXsrv on Windows, https://vcxsrv.com/
Then, in your WSL terminal:

- export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):0
- You can add that line to your ~/.bashrc or ~/.zshrc to make it permanent.
### 4. Clone the Repository
- git clone https://github.com/datamann1013/User_Functionality_WSL.git 
- cd User_Functionality_WSL/projects/hidden_toolbar
### 5. Add Icons
Place your icons in the icons/ folder:
- terminal.png 
- filemanager.png 
- launcher.png
Use 32x32px PNGs for best results.
### 6. Run the Toolbar
Option A: Run manually
- cd src python3 main.py
Option B: Run with fullscreen detection
- chmod +x ../detect_fullscreen.sh ../detect_fullscreen.sh & python3 src/main.py &
### 7. Autostart on Login (Optional)
If you're using Openbox or another window manager, add this to your autostart file (e.g., ~/.config/openbox/autostart):
- /path/to/User_Functionality_WSL/projects/hidden_toolbar/detect_fullscreen.sh & python3 /path/to/User_Functionality_WSL/projects/hidden_toolbar/src/main.py &
Replace /path/to/ with the actual path to your cloned repo.
### 8. Security Notes
- Do not run the toolbar as root. 
- Only use trusted icons and scripts. 
- Avoid embedding sensitive commands in the launcher.