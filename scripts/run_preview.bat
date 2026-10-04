@echo off
setlocal
cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
  echo ERROR: Python virtual environment not found. Run setup_windows.bat first.
  pause
  exit /b 1
)

set "PYTHONPATH=%CD%\src"
".venv\Scripts\python.exe" -m weekly_clean_fuels_digest.main
set EXIT_CODE=%errorlevel%
if %EXIT_CODE%==0 start "" "runtime\output\weekly_digest_preview.html"
pause
exit /b %EXIT_CODE%

