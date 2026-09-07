#!/usr/bin/env bash
# Запуск musslop. Использование: ./run.sh [порт]  (или PORT=8801 ./run.sh)
set -e
cd "$(dirname "$0")"
PORT="${1:-${PORT:-8801}}"

# Освободить порт, если занят старым процессом
OLD=$(lsof -ti tcp:"$PORT" 2>/dev/null || ss -tlnp 2>/dev/null | grep ":$PORT " | grep -o 'pid=[0-9]*' | cut -d= -f2 | head -1)
if [ -n "$OLD" ]; then
  echo "Порт $PORT занят (pid $OLD) — останавливаю старый процесс"
  kill "$OLD" 2>/dev/null || true
  sleep 1
fi

command -v ffmpeg >/dev/null || { echo "ОШИБКА: ffmpeg не найден в PATH"; exit 1; }
python3 -c "import fastapi, uvicorn, librosa" 2>/dev/null || {
  echo "Зависимости не установлены. Выполните: pip install -r requirements.txt"; exit 1; }

# ИИ-анализ: автоматически подхватываем локальный .venv-ai (см. ./setup-ai.sh)
if [ -z "$MUSSLOP_DEEP_PY" ] && [ -x ".venv-ai/bin/python" ]; then
  export MUSSLOP_DEEP_PY="$(pwd)/.venv-ai/bin/python"
fi
if [ -n "$MUSSLOP_DEEP_PY" ] && [ -x "$MUSSLOP_DEEP_PY" ]; then
  echo "ИИ-анализ: доступен ($MUSSLOP_DEEP_PY)"
else
  echo "ИИ-анализ: недоступен (установка: ./setup-ai.sh)"
fi

# Прекомпиляция JSX (необязательно: собранный app.js уже лежит в репозитории).
# Пересборка нужна только после правок frontend/index.html.
if [ frontend/index.html -nt frontend/index.prod.html ] 2>/dev/null; then
  python3 tools/build.py 2>/dev/null && echo "Frontend пересобран (app.js)" \
    || echo "ВНИМАНИЕ: index.html новее сборки, а quickjs нет (pip install quickjs) — будет dev-режим с Babel"
fi

echo "Запуск: http://localhost:$PORT (лог: server.log)"
exec python3 -m uvicorn backend.main:app --host 0.0.0.0 --port "$PORT" 2>&1 | tee server.log
