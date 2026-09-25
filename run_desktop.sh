#!/usr/bin/env bash
# ==============================================================================
# Sage AI - Linux & macOS Launcher
# Automatically detects virtual environment, checks dependencies, and launches Sage AI.
# ==============================================================================

set -e

# Navigate to script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 1. Detect or create virtual environment
if [ -d ".venv" ]; then
    PYTHON_BIN=".venv/bin/python"
elif [ -d "venv" ]; then
    PYTHON_BIN="venv/bin/python"
else
    echo "Creating virtual environment (.venv)..."
    python3 -m venv .venv
    PYTHON_BIN=".venv/bin/python"
    echo "Installing dependencies from requirements.txt..."
    "$PYTHON_BIN" -m pip install --upgrade pip
    "$PYTHON_BIN" -m pip install -r requirements.txt
fi

# 2. Launch Sage AI
echo "Starting Sage AI..."
exec "$PYTHON_BIN" main.py "$@"
