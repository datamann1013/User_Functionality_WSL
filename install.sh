#!/bin/bash
# Installation script for User Functionality WSL project

set -e  # Exit on any error

echo "🚀 Installing User Functionality WSL Dependencies"
echo "=================================================="

# Check Python version
python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "📋 Python version: $python_version"

# Simple version check without bc
if python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"; then
    echo "✅ Python 3.8+ detected"
else
    echo "❌ Python 3.8+ required. Current version: $python_version"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "🔧 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install ErrorLogger dependencies
echo "📦 Installing ErrorLogger dependencies..."
cd projects/ErrorLogger
pip install -e .
cd ../..

# Install AI Service dependencies  
echo "📦 Installing AI Service dependencies..."
cd projects/ai_service/backend
pip install -r requirements.txt
cd ../../..

# Install frontend dependencies
if command -v npm &> /dev/null; then
    echo "📦 Installing frontend dependencies..."
    cd projects/ai_service/frontend
    npm install
    cd ../../..
else
    echo "⚠️  npm not found. Skipping frontend dependencies."
    echo "   Install Node.js to install frontend dependencies."
fi

# Copy environment files
echo "🔧 Setting up environment files..."
if [ ! -f "projects/ai_service/backend/.env" ]; then
    cp projects/ai_service/backend/.env.example projects/ai_service/backend/.env
    echo "✅ Created AI service .env file"
fi

if [ ! -f "projects/ErrorLogger/.env" ]; then
    cp projects/ErrorLogger/.env.example projects/ErrorLogger/.env  
    echo "✅ Created ErrorLogger .env file"
fi

echo ""
echo "✅ Installation complete!"
echo ""

# Run validation within the virtual environment
echo "🔍 Validating installation..."
python3 validate_deps.py
validation_result=$?

echo ""
if [ $validation_result -eq 0 ]; then
    echo "🎉 All dependencies validated successfully!"
else
    echo "⚠️  Some dependencies may need attention, but core components should work."
fi

echo ""
echo "🚀 Quick Start:"
echo "   1. Activate the virtual environment: source venv/bin/activate"
echo "   2. Start ErrorLogger: cd projects/ErrorLogger && python error_server.py"
echo "   3. Start AI Service: cd projects/ai_service/backend && python app.py"
echo "   4. Start Frontend: cd projects/ai_service/frontend && npm start"
echo ""
echo "📚 Check the .env files to customize configuration"
