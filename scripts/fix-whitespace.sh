#!/bin/bash
# Quick script to fix trailing whitespace in Python files

echo "Fixing trailing whitespace in Python files..."

# Remove trailing whitespace from all Python files
find . -name "*.py" -not -path "./venv/*" -not -path "./.env/*" -exec sed -i 's/[[:space:]]*$//' {} +

echo "Trailing whitespace cleaned up!"
