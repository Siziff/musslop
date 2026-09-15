@echo off
rem Optional AI engine for Windows: SongFormer (structure) + Beat This! (beats).
rem Creates a dedicated venv in .venv-songformer\ — run.bat picks it up automatically.
rem Takes ~10-15 minutes and ~4 GB of disk. Needs git in PATH (git-scm.com).
setlocal
cd /d "%~dp0"

echo == musslop AI setup: SongFormer + Beat This! (Windows) ==

where python >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python not found in PATH. Install from https://python.org
  pause & exit /b 1
)
where git >nul 2>nul
if errorlevel 1 (
  echo ERROR: git not found in PATH. Install from https://git-scm.com
  pause & exit /b 1
)

set VENVPY=.venv-songformer\Scripts\python.exe

if not exist "%VENVPY%" (
  echo [1/5] Creating venv in .venv-songformer ...
  python -m venv .venv-songformer
)

echo [2/5] Installing PyTorch (this is the big download) ...
"%VENVPY%" -m pip install --quiet --upgrade pip
rem CUDA build if an NVIDIA GPU is present, CPU otherwise
where nvidia-smi >nul 2>nul
if errorlevel 1 (
  "%VENVPY%" -m pip install --quiet torch==2.6.0 torchaudio==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cpu
) else (
  "%VENVPY%" -m pip install --quiet torch==2.6.0 torchaudio==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cu126
)
if errorlevel 1 ( echo ERROR: PyTorch install failed. & pause & exit /b 1 )

echo [3/5] Installing dependencies (transformers, muq, beat_this, msaf ...) ...
"%VENVPY%" -m pip install --quiet "transformers==4.51.1" numpy librosa muq beat_this ema_pytorch loguru omegaconf einops mir_eval msaf x_transformers soundfile demucs
if errorlevel 1 ( echo ERROR: dependency install failed. & pause & exit /b 1 )

echo [4/5] Cloning SongFormer sources + downloading checkpoints (~1.4 GB) ...
if not exist ".venv-songformer\src" (
  git clone --depth 1 https://github.com/ASLP-lab/SongFormer .venv-songformer\src
  pushd .venv-songformer\src
  git submodule update --init --recursive
  popd
)
pushd .venv-songformer\src\src\SongFormer
"%~dp0.venv-songformer\Scripts\python.exe" utils\fetch_pretrained.py
popd
if errorlevel 1 ( echo ERROR: checkpoint download failed. & pause & exit /b 1 )

echo [5/5] Verifying ...
set SONGFORMER_SRC=%~dp0.venv-songformer\src
if not exist ".venv-songformer\src\src\third_party\musicfm\model" (
  echo ERROR: musicfm submodule missing — re-running git submodule update...
  pushd .venv-songformer\src
  git submodule update --init --recursive
  popd
)
if not exist ".venv-songformer\src\src\third_party\musicfm\model" (
  echo ERROR: submodules failed to clone. Check your network/git and re-run.
  pause & exit /b 1
)
"%VENVPY%" -c "import os, torch; assert os.path.isdir(os.path.join(os.environ['SONGFORMER_SRC'],'src','SongFormer','ckpts')), 'checkpoints missing'; import beat_this, muq; print('OK: SongFormer + Beat This! ready, device:', 'cuda' if torch.cuda.is_available() else 'cpu')"
if errorlevel 1 ( echo ERROR: verification failed. & pause & exit /b 1 )

echo.
echo Done! Start run.bat — the SongFormer button will appear automatically.
echo.
echo Note: the second engine (All-In-One) is not supported on Windows:
echo its NATTEN dependency requires building from source with MSVC.
echo Use WSL2 (Ubuntu) if you need it — setup-ai-allin1.sh works there.
pause
