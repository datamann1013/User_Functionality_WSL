# 🧰 User Functionality WSL

**A modular collection of quality-of-life tools for users combining Windows and Linux (WSL2).**

This repository is a growing set of small, focused systems that improve the experience of using
Linux under Windows. Each tool lives in its own folder under `projects/`, and can be used 
independently or together.

> **Current Status**: Active development on AI Service Platform (Phase 1 - MVP Completion)  
> **Last Updated**: October 16, 2025

---

## 🚀 Quick Start - AI Service Platform

**Featured Project!** Complete AI service platform with multi-agent chat, model management, and centralized logging:

```bash
# One-command setup and start all services
./projects/ai_service/start_ai_service.sh
```

**Services Started:**
- 🤖 AI Service Backend (Port 5000)
- � React Frontend (Port 3000) - *Currently in development*
- 🔧 Ollama Model Service (Port 5002)
- 📊 ErrorLogger Service (Port 5001)

�🎯 **See [ai_service/README.md](projects/ai_service/README.md) for detailed documentation and roadmap**

---

## 🧩 What You'll Find Here

### 🤖 [AI Service Platform](projects/ai_service/) 
**Status**: 🚧 Pre-Alpha (Phase 1 Development)
- Multi-agent AI chat system with memory capabilities
- Support for multiple Ollama models (llama3.2, gemma:2b, codellama:7b)
- Centralized error logging and monitoring integration
- **Current Focus**: Frontend implementation and security hardening

### 🔍 [ErrorLogger](projects/ErrorLogger/)
**Status**: ✅ Production Ready
- Centralized error logging and monitoring system
- Used across all projects for unified error tracking
- Web interface for error analysis and debugging
- Remote logging capabilities with structured error codes

### 🪟 [Hidden Toolbar](projects/hidden_toolbar/)
**Status**: ✅ Stable
- Hover-activated launcher panel for Openbox window managers
- Customizable icons and application shortcuts
- Fullscreen detection and auto-hide functionality
- Perfect for minimal desktop setups

### 🔧 [Shared Utilities](projects/shared_utils/)
**Status**: ✅ Supporting Library
- Common constants and utilities used across projects
- Shared configuration management
- Cross-project compatibility helpers

---

## 📁 Current Project Structure

```
User_Functionality_WSL/
├── README.md                        # This file
├── LICENSE                          # MIT License
├── start_ai_service.sh             # Quick start script
├── projects/
│   ├── ai_service/                 # 🤖 AI Service Platform (Main Project)
│   │   ├── README.md               # Detailed docs + roadmap
│   │   ├── start_ai_service.sh     # Service orchestration
│   │   ├── backend/                # Flask API (80% complete)
│   │   ├── frontend/               # React UI (5% complete - Priority!)
│   │   ├── ollama_service/         # AI model service wrapper
│   │   └── bootstrap/              # Setup and initialization
│   ├── ErrorLogger/                # 🔍 Centralized logging system
│   │   ├── README.md
│   │   ├── logger.py               # Core logging functionality
│   │   ├── error_server.py         # Web interface
│   │   └── start_errorlogger.sh    # Service startup
│   ├── hidden_toolbar/             # 🪟 Desktop launcher panel
│   │   ├── README.md
│   │   ├── launcher.py             # Main application
│   │   ├── src/                    # Source modules
│   │   └── icons/                  # UI icons
│   └── shared_utils/               # 🔧 Common utilities
│       └── constants.py            # Shared constants
└── venv/                           # Python virtual environment
```

---

## 🏗️ Development Status Overview

| Project | Backend | Frontend | Security | Documentation | Priority |
|---------|---------|----------|----------|---------------|----------|
| **AI Service** | 80% ✅ | 5% ❌ | 20% ⚠️ | 90% ✅ | 🚨 Critical |
| **ErrorLogger** | 100% ✅ | 100% ✅ | 70% ✅ | 85% ✅ | ✅ Complete |
| **Hidden Toolbar** | 100% ✅ | 100% ✅ | N/A | 80% ✅ | ✅ Stable |
| **Shared Utils** | 100% ✅ | N/A | N/A | 60% ⚠️ | 🔄 Maintenance |

---

## 🎯 Current Development Focus

### Phase 1: AI Service MVP Completion (Weeks 1-2)
- **Critical**: Implement missing React frontend components
- **Critical**: Add basic authentication and security
- **High**: Complete user flow testing and validation

### Next Phases
- **Phase 2**: Production deployment and scaling (Weeks 3-4)
- **Phase 3**: Advanced features and integrations (Weeks 5-8)
- **Phase 4**: Enterprise features and compliance (Weeks 9-12)

*See [AI Service Roadmap](projects/ai_service/README.md#-development-roadmap) for detailed timeline*

---

## 🚀 Getting Started

### Prerequisites
- **WSL2** with Ubuntu 20.04+ (or native Linux)
- **Python 3.8+** with pip
- **Node.js 16+** with npm
- **Git** for version control

### Quick Setup
```bash
# Clone the repository
git clone <repository-url>
cd User_Functionality_WSL

# Set up Python environment
python -m venv venv
source venv/bin/activate  # Linux/WSL
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Start AI Service (includes all components)
./projects/ai_service/start_ai_service.sh
```

### Individual Project Setup
Each project can be run independently:
```bash
# ErrorLogger service
./projects/ErrorLogger/start_errorlogger.sh

# Hidden Toolbar (for desktop environments)
cd projects/hidden_toolbar && python launcher.py
```

---

## 📋 Contributing & Development

### Current Priorities
1. **AI Service Frontend** - React components need implementation
2. **Security Hardening** - Authentication and input validation
3. **Documentation** - API docs and user guides
4. **Testing** - Unit tests and integration testing

### Development Workflow
- All changes should maintain compatibility with ErrorLogger integration
- Follow existing code architecture and patterns
- Test across multiple environments (WSL2, native Linux)
- Update relevant README files with changes

### Getting Help
- **Architecture Questions**: See individual project README files
- **Error Tracking**: Check ErrorLogger web interface at http://localhost:5001
- **Development Issues**: Focus on current phase priorities
- **Feature Requests**: Consider current roadmap phases

---

## 📜 License

MIT License - See [LICENSE](LICENSE) file for details.

---

*This README reflects the current state as of October 16, 2025. The repository is in active development with primary focus on completing the AI Service Platform MVP.*ionality WSL

**A modular collection of quality-of-life tools for users combining Windows and Linux (WSL2).**

This repository is a growing set of small, focused systems that improve the experience of using
Linux under Windows. Each tool lives in its own folder under `projects/`, and can be used 
independently or together.
---

## 🧩 What You’ll Find Here

- 🪟 [hidden_toolbar/](projects/hidden_toolbar/README.md) — A hover-activated launcher bump for Openbox
- 🧪 More tools coming soon...

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
