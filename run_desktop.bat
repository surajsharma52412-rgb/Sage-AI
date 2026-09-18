@echo off
setlocal

cd /d "%~dp0"

:: 1. If virtual environment exists, launch directly
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" main.py
    exit /b 0
)

if exist ".venv\Scripts\python.exe" (
    start "" ".venv\Scripts\python.exe" main.py
    exit /b 0
)

:: 2. If virtual environment doesn't exist, create it and install requirements automatically
echo [Sage AI] Setting up virtual environment for this computer...
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [Sage AI Error] Python was not found in PATH. Please install Python 3.10+ from python.org
    pause
    exit /b 1
)

python -m venv .venv
if %ERRORLEVEL% neq 0 (
    echo [Sage AI Error] Failed to create .venv.
    pause
    exit /b 1
)

echo [Sage AI] Installing dependencies...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt

echo [Sage AI] Setup complete. Launching Sage AI...
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" main.py
) else (
    start "" ".venv\Scripts\python.exe" main.py
)
exit /b 0
