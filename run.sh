#!/usr/bin/env bash
# Запуск musslop. Использование: ./run.sh [порт]  (или PORT=8801 ./run.sh)
set -e
cd "$(dirname "$0")"
PORT="${1:-${PORT:-8801}}"

# Локальные секреты/настройки: .env в корне проекта (не коммитится).
# Пример: HF_TOKEN=hf_xxxxx
if [ -f ".env" ]; then
  set -a; . ./.env; set +a
  echo "Загружен .env"
fi

# Освободить порт, если занят старым процессом (может быть несколько pid)
OLD=$(lsof -ti tcp:"$PORT" 2>/dev/null || ss -tlnp 2>/dev/null | grep ":$PORT " | grep -o 'pid=[0-9]*' | cut -d= -f2 | head -1)
if [ -n "$OLD" ]; then
  echo "Порт $PORT занят (pid: $(echo $OLD | tr '\n' ' ')) — останавливаю"
  for pid in $OLD; do kill "$pid" 2>/dev/null || true; done
  sleep 1
  # если не умерли — жёстко
  STILL=$(lsof -ti tcp:"$PORT" 2>/dev/null || true)
  if [ -n "$STILL" ]; then
    for pid in $STILL; do kill -9 "$pid" 2>/dev/null || true; done
    sleep 1
  fi
  if [ -n "$(lsof -ti tcp:"$PORT" 2>/dev/null || true)" ]; then
    echo "ОШИБКА: порт $PORT так и занят — освободите вручную: lsof -ti tcp:$PORT | xargs kill -9"
    exit 1
  fi
fi

command -v ffmpeg >/dev/null || { echo "ОШИБКА: ffmpeg не найден в PATH"; exit 1; }
python3 -c "import fastapi, uvicorn, librosa" 2>/dev/null || {
  echo "Зависимости не установлены. Выполните: pip install -r requirements.txt"; exit 1; }
if python3 -c "import yt_dlp" 2>/dev/null || command -v yt-dlp >/dev/null; then
  echo "URL import (yt-dlp): available"
else
  echo "URL import (yt-dlp): not installed (pip3 install yt-dlp)"
fi

# ИИ-движок #1: All-In-One (./setup-ai-allin1.sh -> .venv-ai)
if [ -z "$MUSSLOP_DEEP_PY" ] && [ -x ".venv-ai/bin/python" ]; then
  export MUSSLOP_DEEP_PY="$(pwd)/.venv-ai/bin/python"
fi
if [ -n "$MUSSLOP_DEEP_PY" ] && [ -x "$MUSSLOP_DEEP_PY" ]; then
  echo "AI engine All-In-One: available"
else
  echo "AI engine All-In-One: not installed (./setup-ai-allin1.sh)"
fi
# ИИ-движок #2: SongFormer + Beat This! (./setup-ai-songformer.sh -> .venv-songformer)
if [ -z "$MUSSLOP_SONGFORMER_PY" ] && [ -x ".venv-songformer/bin/python" ]; then
  export MUSSLOP_SONGFORMER_PY="$(pwd)/.venv-songformer/bin/python"
  export SONGFORMER_SRC="$(pwd)/.venv-songformer/src"
fi
if [ -n "$MUSSLOP_SONGFORMER_PY" ] && [ -x "$MUSSLOP_SONGFORMER_PY" ]; then
  echo "AI engine SongFormer: available"
else
  echo "AI engine SongFormer: not installed (./setup-ai-songformer.sh)"
fi

# Прекомпиляция JSX (необязательно: собранный app.js уже лежит в репозитории).
# Пересборка нужна только после правок frontend/index.html.
if [ frontend/index.html -nt frontend/index.prod.html ] 2>/dev/null; then
  python3 tools/build.py 2>/dev/null && echo "Frontend пересобран (app.js)" \
    || echo "ВНИМАНИЕ: index.html новее сборки, а quickjs нет (pip install quickjs) — будет dev-режим с Babel"
fi

echo "Запуск: http://localhost:$PORT (лог: server.log)"
exec python3 -m uvicorn backend.main:app --host 0.0.0.0 --port "$PORT" 2>&1 | tee server.log
