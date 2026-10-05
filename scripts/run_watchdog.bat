@echo off
setlocal
cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
  echo ERROR: Python virtual environment not found. Run setup_windows.bat first.
  exit /b 1
)

rem Deliberately no OPENAI_API_KEY check here: a missing key is one of the
rem failures this watchdog exists to report, so it must be able to run without it.
set "PYTHONPATH=%CD%\src"
".venv\Scripts\python.exe" -m weekly_clean_fuels_digest.watchdog %*
exit /b %errorlevel%
