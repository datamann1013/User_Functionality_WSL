#!/usr/bin/env python3
"""
Dependency validation script for User Functionality WSL project
"""
import sys
import importlib
import subprocess  # nosec B404
import os


def check_import(module_name, optional=False):
    """Check if a module can be imported"""
    try:
        importlib.import_module(module_name)
        print(f"✅ {module_name}")
        return True
    except ImportError as e:
        status = "⚠️" if optional else "❌"
        print(f"{status} {module_name} - {str(e)}")
        return False


def check_backend_dependencies():
    """Check AI Service backend dependencies"""
    print("\n📦 AI Service Backend Dependencies:")
    print("=" * 40)

    required = [
        "flask",
        "torch",
        "transformers",
        "huggingface_hub",
        "requests",
        "pytest",
        "dotenv",
        "numpy",
    ]

    optional = ["accelerate", "safetensors", "tokenizers", "psutil"]

    all_good = True
    for module in required:
        if not check_import(module):
            all_good = False

    for module in optional:
        check_import(module, optional=True)

    return all_good


def check_errorlogger_dependencies():
    """Check ErrorLogger dependencies"""
    print("\n📦 ErrorLogger Dependencies:")
    print("=" * 30)

    required = ["flask", "werkzeug", "requests", "dotenv"]

    all_good = True
    for module in required:
        if not check_import(module):
            all_good = False

    return all_good


def check_project_imports():
    """Check if project modules can be imported"""
    print("\n🔧 Project Module Imports:")
    print("=" * 30)

    # Add project root to path
    project_root = os.path.dirname(os.path.abspath(__file__))
    projects_path = os.path.join(project_root, "projects")
    sys.path.insert(0, projects_path)

    modules_to_test = [
        "ErrorLogger.error_codes",
        "ErrorLogger.logger",
        "ErrorLogger.error_handler",
    ]

    all_good = True
    for module in modules_to_test:
        if not check_import(module):
            all_good = False

    return all_good


def check_environment_files():
    """Check if environment files exist"""
    print("\n⚙️ Environment Configuration:")
    print("=" * 30)

    env_files = ["projects/ai_service/backend/.env", "projects/ErrorLogger/.env"]

    all_good = True
    for env_file in env_files:
        if os.path.exists(env_file):
            print(f"✅ {env_file}")
        else:
            print(f"⚠️ {env_file} - Missing (using defaults)")

    return all_good


def main():
    print("🔍 User Functionality WSL - Dependency Validation")
    print("=" * 50)

    backend_ok = check_backend_dependencies()
    errorlogger_ok = check_errorlogger_dependencies()
    imports_ok = check_project_imports()
    env_ok = check_environment_files()

    print("\n📋 Summary:")
    print("=" * 15)

    if backend_ok and errorlogger_ok and imports_ok:
        print("✅ All critical dependencies are available")
        print("🚀 Project should run successfully")
        return 0
    else:
        print("❌ Some dependencies are missing")
        print("💡 Run './install.sh' to install missing dependencies")
        return 1


if __name__ == "__main__":
    sys.exit(main())
