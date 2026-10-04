@echo off
setlocal
cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
  echo ERROR: Python virtual environment not found. Run setup_windows.bat first.
  exit /b 1
)

if "%OPENAI_API_KEY%"=="" (
  echo ERROR: OPENAI_API_KEY is not available to this Windows user.
  exit /b 1
)

set "PYTHONPATH=%CD%\src"
".venv\Scripts\python.exe" -m weekly_clean_fuels_digest.main --send
exit /b %errorlevel%
