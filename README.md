# 🧰 User Functionality WSL

**A modular collection of quality-of-life tools for users combining Windows and Linux (WSL2).**

[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=datamann1013_User_Functionality_WSL&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=datamann1013_User_Functionality_WSL)

This repository is a growing set of small, focused systems that improve the experience of using
Linux under Windows. Each tool lives in its own folder under `projects/`, and can be used 
independently or together.
---

## 🧩 What You’ll Find Here

- 🪟 [hidden_toolbar](projects/hidden_toolbar/README.md) — A hover-activated launcher bump for Openbox
- 🧪 More tools coming soon...

## Ideas for later projects:
- 🖥️ Computer communication - An application to use one computer to control another, e.g., using a phone to control a desktop.
- 📊 System monitoring - A tool to monitor system performance across multiple computers, e.g., monitoring CPU usage on a desktop from a laptop.
- 🔐 Security tool - A tool to manage security settings across multiple computers, e.g., managing firewall settings on a desktop from a laptop.

---

## 📁 Folder Structure
```
User_Functionality_WSL/
├── README.md                        
├── LICENSE
├── projects/
│   ├── hidden_toolbar/
│   │   ├── README.md
│   │   ├── launcher.py
│   │   ├── notes.md
│   │   ├── icons/
│   │   ├── style.css
│   │   ├── config.json
│   │   ├── detect_fullscreen.sh
│   │   └── src/
│   │       ├── __init__.py
│   │       ├── main.py
│   │       ├── panel.py
│   │       ├── visibility.py
│   │       └── utils.py
│   └── later project
```
