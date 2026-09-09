#!/usr/bin/env bash
# One-command setup for musslop (core, no AI engines).
# Creates .venv/ and installs everything needed for ./run.sh.
#
# Usage: ./setup.sh
set -e
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"

echo "== musslop setup =="
$PY -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10+ required"' \
  || { echo "ERROR: Python 3.10+ required"; exit 1; }
command -v ffmpeg >/dev/null || {
  echo "ERROR: ffmpeg not found in PATH."
  echo "  macOS:  brew install ffmpeg"
  echo "  Ubuntu: sudo apt install ffmpeg"
  exit 1
}

if [ ! -x ".venv/bin/python" ]; then
  echo "[1/2] Creating venv in .venv ..."
  $PY -m venv .venv
fi
echo "[2/2] Installing dependencies ..."
./.venv/bin/pip install --quiet --upgrade pip
./.venv/bin/pip install --quiet -r requirements.txt

./.venv/bin/python -c "import fastapi, uvicorn, librosa, yt_dlp; print('OK: core dependencies ready')"

echo
echo "Done! Start the app:   ./run.sh"
echo "Optional AI engines:   ./setup-ai-songformer.sh   ./setup-ai-allin1.sh"
