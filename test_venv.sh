#!/bin/bash
# Quick test script to verify the virtual environment setup

echo "🧪 Testing Virtual Environment Setup"
echo "===================================="

if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Run ./install.sh first."
    exit 1
fi

echo "🔧 Activating virtual environment..."
source venv/bin/activate

echo "🐍 Python in virtual environment:"
which python
python --version

echo ""
echo "📦 Testing key imports in virtual environment:"

echo -n "  Flask: "
python -c "import flask; print('✅ Available')" 2>/dev/null || echo "❌ Missing"

echo -n "  Torch: "
python -c "import torch; print('✅ Available')" 2>/dev/null || echo "❌ Missing"

echo -n "  Transformers: "
python -c "import transformers; print('✅ Available')" 2>/dev/null || echo "❌ Missing"

echo -n "  ErrorLogger: "
python -c "import sys; sys.path.insert(0, 'projects'); from ErrorLogger.error_codes import ERROR_CODE_DEFINITIONS; print('✅ Available')" 2>/dev/null || echo "❌ Missing"

echo ""
echo "🔍 Running full validation..."
python validate_deps.py

echo ""
echo "💡 To use the virtual environment:"
echo "   source venv/bin/activate"
