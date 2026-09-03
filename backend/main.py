# Musslop — FastAPI-сервер: загрузка трека, анализ, раздача аудио и UI.

from __future__ import annotations

import os
import uuid
import shutil
import subprocess
import tempfile

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .analysis import analyze

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="Musslop")

# id -> {"path": ..., "name": ...}
TRACKS: dict[str, dict] = {}

ALLOWED_EXT = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac", ".opus", ".webm"}


def _to_wav(src: str, dst: str) -> None:
    """Перекодировать в WAV (для надёжного decodeAudioData в браузере и librosa)."""
    subprocess.run(
        ["ffmpeg", "-y", "-i", src, "-ac", "2", "-ar", "44100", dst],
        check=True, capture_output=True,
    )


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"Неподдерживаемый формат: {ext}")

    track_id = uuid.uuid4().hex[:12]
    raw_path = os.path.join(UPLOAD_DIR, f"{track_id}{ext}")
    with open(raw_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    wav_path = os.path.join(UPLOAD_DIR, f"{track_id}.wav")
    if ext != ".wav":
        try:
            _to_wav(raw_path, wav_path)
        except subprocess.CalledProcessError:
            os.remove(raw_path)
            raise HTTPException(400, "Не удалось декодировать файл")
        os.remove(raw_path)

    TRACKS[track_id] = {"path": wav_path, "name": file.filename}
    return {"track_id": track_id, "name": file.filename}


@app.get("/api/analyze/{track_id}")
def analyze_track(track_id: str, n_segments: int | None = Query(None, ge=2, le=24)):
    track = TRACKS.get(track_id)
    if not track:
        raise HTTPException(404, "Трек не найден")
    result = analyze(track["path"], n_segments=n_segments)
    result["track_id"] = track_id
    result["name"] = track["name"]
    return result


@app.get("/api/audio/{track_id}")
def get_audio(track_id: str):
    track = TRACKS.get(track_id)
    if not track:
        raise HTTPException(404, "Трек не найден")
    return FileResponse(track["path"], media_type="audio/wav")


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
