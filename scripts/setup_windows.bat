@echo off
setlocal
cd /d "%~dp0.."

where py >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python launcher 'py' was not found. Install Python 3.11 or later.
  pause
  exit /b 1
)

py -3 -m venv .venv
if errorlevel 1 exit /b 1

".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 exit /b 1

".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

if not exist runtime\secrets mkdir runtime\secrets
if not exist runtime\output mkdir runtime\output
if not exist runtime\state mkdir runtime\state
if not exist runtime\logs mkdir runtime\logs

echo.
echo Setup complete.
echo 1. Put Google OAuth credentials at runtime\secrets\credentials.json
echo 2. Set OPENAI_API_KEY as described in README.md
echo 3. Double-click scripts\run_preview.bat for the first authorization and preview
pause
