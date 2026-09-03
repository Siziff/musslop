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

echo "Запуск: http://localhost:$PORT (лог: server.log)"
exec python3 -m uvicorn backend.main:app --host 0.0.0.0 --port "$PORT" 2>&1 | tee server.log
