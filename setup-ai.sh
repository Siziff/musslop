#!/usr/bin/env bash
# Установка опциональных ИИ-компонентов (All-In-One structure analyzer).
# Создаёт отдельный venv в .venv-ai/ — run.sh подхватит его автоматически.
#
# Использование: ./setup-ai.sh
# Займёт ~10 минут и ~2.5 GB диска (torch, demucs, madmom, allin1).
set -e
cd "$(dirname "$0")"

VENV=".venv-ai"
PY="${PYTHON:-python3}"

echo "== musslop AI setup =="
$PY -c 'import sys; assert sys.version_info >= (3, 10), "нужен Python 3.10+"' \
  || { echo "ОШИБКА: нужен Python 3.10+"; exit 1; }

if [ -x "$VENV/bin/python" ] && "$VENV/bin/python" -c "import allin1" 2>/dev/null; then
  echo "Уже установлено ($VENV). Для переустановки удалите каталог: rm -rf $VENV"
  exit 0
fi

echo "[1/4] Создаю venv в $VENV ..."
$PY -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip

echo "[2/4] Устанавливаю PyTorch (CPU/MPS на macOS, CUDA — если есть) ..."
OS="$(uname -s)"
# Пин torch 2.6: allin1 требует NATTEN 0.17.x, который собран/собирается под torch<=2.6
if [ "$OS" = "Darwin" ]; then
  "$VENV/bin/pip" install --quiet torch==2.6.0 torchaudio==2.6.0
else
  # Linux: если есть nvidia-smi — CUDA-сборка, иначе CPU
  if command -v nvidia-smi >/dev/null 2>&1; then
    "$VENV/bin/pip" install --quiet torch==2.6.0 torchaudio==2.6.0 \
      --index-url https://download.pytorch.org/whl/cu126
  else
    "$VENV/bin/pip" install --quiet torch==2.6.0 torchaudio==2.6.0 \
      --index-url https://download.pytorch.org/whl/cpu
  fi
fi

echo "[3/4] Устанавливаю madmom, allin1 и совместимый NATTEN ..."
"$VENV/bin/pip" install --quiet "git+https://github.com/CPJKU/madmom"
"$VENV/bin/pip" install --quiet allin1

# allin1 тянет свежий natten (0.21+), где нет нужного API — заменяем на 0.17.5
PYTAG=$("$VENV/bin/python" -c "import sys; print(f'cp{sys.version_info.major}{sys.version_info.minor}')")
if [ "$OS" = "Linux" ] && command -v nvidia-smi >/dev/null 2>&1; then
  "$VENV/bin/pip" install --quiet --force-reinstall \
    "https://github.com/SHI-Labs/NATTEN/releases/download/v0.17.5/natten-0.17.5%2Btorch260cu126-${PYTAG}-${PYTAG}-linux_x86_64.whl" \
    || { echo "ОШИБКА: колесо NATTEN не подошло — см. https://whl.natten.org"; exit 1; }
else
  # macOS/CPU: сборка из исходников (нужен компилятор; на маке — Xcode CLT)
  if [ "$OS" = "Darwin" ] && ! xcode-select -p >/dev/null 2>&1; then
    echo "ОШИБКА: нужен Xcode Command Line Tools: xcode-select --install"; exit 1
  fi
  echo "  (сборка NATTEN 0.17.5 из исходников, 2-5 минут...)"
  "$VENV/bin/pip" install --quiet --force-reinstall --no-build-isolation \
    "natten==0.17.5" \
    || { echo "ОШИБКА: NATTEN не собрался. Проверьте компилятор (clang/gcc)"; exit 1; }
fi

# allin1 может требовать старый API natten — шим совместимости
SITE=$("$VENV/bin/python" -c "import site; print(site.getsitepackages()[0])")
if ! "$VENV/bin/python" -c "from natten.functional import natten1dav" 2>/dev/null \
   && "$VENV/bin/python" -c "from natten.functional import na1d_qk" 2>/dev/null; then
  cat > "$SITE/natten_compat.py" <<'EOF'
from natten.functional import na1d_qk, na1d_av, na2d_qk, na2d_av
def natten1dqkrpb(q, k, rpb, ks, dil): return na1d_qk(q, k, ks, dil, rpb=rpb)
def natten1dav(a, v, ks, dil): return na1d_av(a, v, ks, dil)
def natten2dqkrpb(q, k, rpb, ks, dil): return na2d_qk(q, k, ks, dil, rpb=rpb)
def natten2dav(a, v, ks, dil): return na2d_av(a, v, ks, dil)
EOF
  sed -i.bak 's/from natten.functional import natten1dav, natten1dqkrpb, natten2dav, natten2dqkrpb/from natten_compat import natten1dav, natten1dqkrpb, natten2dav, natten2dqkrpb/' \
    "$SITE/allin1/models/dinat.py" && rm -f "$SITE/allin1/models/dinat.py.bak"
  echo "  (применён шим совместимости NATTEN)"
fi

echo "[4/4] Проверяю ..."
"$VENV/bin/python" - <<'EOF'
import allin1, torch
dev = 'cuda' if torch.cuda.is_available() else \
      'mps' if getattr(torch.backends, 'mps', None) and torch.backends.mps.is_available() else 'cpu'
print(f"OK: allin1 работает, устройство: {dev}")
EOF

echo
echo "Готово! Запустите ./run.sh — кнопка '✨ Разделить с ИИ' появится автоматически."
