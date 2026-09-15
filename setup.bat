@echo off
rem One-command setup for musslop on Windows (core, no AI engines).
rem Creates .venv\ and installs everything needed for run.bat.
rem ffmpeg is bundled automatically via the imageio-ffmpeg package.
setlocal
cd /d "%~dp0"

echo == musslop setup (Windows) ==

where python >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python not found. Install Python 3.10+ from https://python.org
  echo        and check "Add python.exe to PATH" in the installer.
  pause
  exit /b 1
)

python -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)"
if errorlevel 1 (
  echo ERROR: Python 3.10+ required. Found:
  python --version
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [1/2] Creating venv in .venv ...
  python -m venv .venv
)

echo [2/2] Installing dependencies ...
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
if errorlevel 1 (
  echo ERROR: dependency installation failed. See messages above.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" -c "import fastapi, uvicorn, librosa, yt_dlp, imageio_ffmpeg; print('OK: core dependencies ready (ffmpeg bundled:', imageio_ffmpeg.get_ffmpeg_exe(), ')')"
if errorlevel 1 (
  echo ERROR: verification failed.
  pause
  exit /b 1
)

echo.
echo Done! Start the app:   run.bat
pause
