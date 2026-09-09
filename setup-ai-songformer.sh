#!/usr/bin/env bash
# Optional AI engine #2: SongFormer (structure, 2025) + Beat This! (beats, 2024).
# Creates a dedicated venv in .venv-songformer/ — run.sh picks it up automatically.
#
# Usage: ./setup-ai-songformer.sh
# Takes ~10 minutes and ~4 GB of disk (torch, MuQ, MusicFM, checkpoints).
# No Demucs, no NATTEN, no compilers needed — plain pip installs.
set -e
cd "$(dirname "$0")"

VENV=".venv-songformer"
PY="${PYTHON:-python3}"

echo "== musslop AI setup: SongFormer + Beat This! =="
$PY -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10+ required"' \
  || { echo "ERROR: Python 3.10+ required"; exit 1; }

if [ -x "$VENV/bin/python" ] && [ -d "$VENV/src/src/SongFormer/ckpts" ] \
   && "$VENV/bin/python" -c "import beat_this, muq" 2>/dev/null; then
  echo "Already installed ($VENV). To reinstall: rm -rf $VENV"
  exit 0
fi

echo "[1/5] Creating venv in $VENV ..."
$PY -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip

echo "[2/5] Installing PyTorch (CUDA / MPS / CPU auto) ..."
OS="$(uname -s)"
if [ "$OS" = "Darwin" ]; then
  "$VENV/bin/pip" install --quiet torch==2.6.0 torchaudio==2.6.0 torchvision==0.21.0
else
  if command -v nvidia-smi >/dev/null 2>&1; then
    "$VENV/bin/pip" install --quiet torch==2.6.0 torchaudio==2.6.0 torchvision==0.21.0 \
      --index-url https://download.pytorch.org/whl/cu126
  else
    "$VENV/bin/pip" install --quiet torch==2.6.0 torchaudio==2.6.0 torchvision==0.21.0 \
      --index-url https://download.pytorch.org/whl/cpu
  fi
fi

echo "[3/5] Installing dependencies (transformers 4.51, muq, beat_this, msaf ...) ..."
"$VENV/bin/pip" install --quiet "transformers==4.51.1" numpy librosa muq beat_this \
  ema_pytorch loguru omegaconf einops mir_eval msaf x_transformers soundfile

echo "[4/5] Cloning SongFormer sources + downloading checkpoints (~1.4 GB) ..."
if [ ! -d "$VENV/src" ]; then
  git clone --depth 1 https://github.com/ASLP-lab/SongFormer "$VENV/src"
  (cd "$VENV/src" && git submodule update --init --recursive 2>/dev/null || true)
fi
VENV_PY="$(pwd)/$VENV/bin/python"
(cd "$VENV/src/src/SongFormer" && "$VENV_PY" utils/fetch_pretrained.py)

echo "[5/5] Verifying ..."
SONGFORMER_SRC="$(pwd)/$VENV/src" "$VENV/bin/python" - <<'EOF'
import os, torch
assert os.path.isdir(os.path.join(os.environ["SONGFORMER_SRC"], "src", "SongFormer", "ckpts")), "checkpoints missing"
import beat_this, muq
dev = 'cuda' if torch.cuda.is_available() else \
      'mps' if getattr(torch.backends, 'mps', None) and torch.backends.mps.is_available() else 'cpu'
print(f"OK: SongFormer + Beat This! ready, device: {dev}")
EOF

echo
echo "Done! Start ./run.sh — the SongFormer engine will appear automatically."
