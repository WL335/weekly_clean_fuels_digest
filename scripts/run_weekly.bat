@echo off
setlocal
cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
  echo ERROR: Python virtual environment not found. Run setup_windows.bat first.
  exit /b 1
)

rem The OPENAI_API_KEY check now lives in the application, so that a missing key is
rem reported through the alert channels instead of only as an exit code here.

set "PYTHONPATH=%CD%\src"
".venv\Scripts\python.exe" -m weekly_clean_fuels_digest.main --send
exit /b %errorlevel%
