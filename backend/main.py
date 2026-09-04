# Musslop — FastAPI-сервер: загрузка трека, анализ, раздача аудио и UI.

from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid

from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Body
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .analysis import analyze, loop_quality

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="Musslop")

APP_VERSION = "0.3.0"


@app.middleware("http")
async def no_html_cache(request, call_next):
    """HTML не кэшируем никогда: иначе браузер может показывать старый UI."""
    response = await call_next(request)
    ct = response.headers.get("content-type", "")
    if "text/html" in ct:
        response.headers["Cache-Control"] = "no-store, must-revalidate"
    return response

# id -> {"orig": path, "wav": path, "name": str, "mime": str}
TRACKS: dict[str, dict] = {}

ALLOWED_EXT = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac", ".opus", ".webm"}
MIME = {
    ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg",
    ".flac": "audio/flac", ".m4a": "audio/mp4", ".aac": "audio/aac",
    ".opus": "audio/ogg", ".webm": "audio/webm",
}


def _meta_path(track_id: str) -> str:
    return os.path.join(UPLOAD_DIR, f"{track_id}.json")


def _restore_tracks() -> None:
    """Восстановить реестр треков после рестарта сервера (по meta-файлам)."""
    for fn in os.listdir(UPLOAD_DIR):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(UPLOAD_DIR, fn)) as f:
                meta = json.load(f)
            if os.path.exists(meta["orig"]) and os.path.exists(meta["wav"]):
                TRACKS[meta["id"]] = meta
        except Exception:
            pass


_restore_tracks()


def _to_wav(src: str, dst: str) -> None:
    """Перекодировать в WAV для librosa (браузеру отдаём оригинал)."""
    subprocess.run(
        ["ffmpeg", "-y", "-i", src, "-ac", "1", "-ar", "22050", dst],
        check=True, capture_output=True,
    )


@app.get("/api/health")
def health():
    return {"status": "ok", "tracks": len(TRACKS)}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"Неподдерживаемый формат: {ext}")

    track_id = uuid.uuid4().hex[:12]
    orig_path = os.path.join(UPLOAD_DIR, f"{track_id}{ext}")
    with open(orig_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # WAV (mono/22050) — только для анализа на сервере
    wav_path = os.path.join(UPLOAD_DIR, f"{track_id}.analysis.wav")
    if ext == ".wav":
        wav_path = orig_path
    else:
        try:
            _to_wav(orig_path, wav_path)
        except subprocess.CalledProcessError:
            os.remove(orig_path)
            raise HTTPException(400, "Не удалось декодировать файл (ffmpeg)")

    meta = {"id": track_id, "orig": orig_path, "wav": wav_path,
            "name": file.filename, "mime": MIME.get(ext, "application/octet-stream"),
            "uploaded_at": int(__import__("time").time())}
    TRACKS[track_id] = meta
    with open(_meta_path(track_id), "w") as f:
        json.dump(meta, f)

    size = os.path.getsize(orig_path)
    return {"track_id": track_id, "name": file.filename, "size": size}


@app.get("/api/tracks")
def list_tracks():
    """История загруженных треков (для повторного открытия с разметкой)."""
    items = []
    for tid, m in TRACKS.items():
        items.append({
            "track_id": tid,
            "name": m.get("name"),
            "uploaded_at": m.get("uploaded_at", 0),
            "has_markup": bool(m.get("markup")),
            "duration": (m.get("markup") or {}).get("duration"),
            "n_segments": len((m.get("markup") or {}).get("segments", []) or []),
        })
    items.sort(key=lambda x: -x["uploaded_at"])
    return {"tracks": items}


@app.post("/api/markup/{track_id}")
def save_markup(track_id: str, markup: dict = Body(...)):
    """Сохранить разметку (segments + downbeats/beats/tempo) рядом с треком."""
    track = TRACKS.get(track_id)
    if not track:
        raise HTTPException(404, "Трек не найден")
    track["markup"] = markup
    with open(_meta_path(track_id), "w") as f:
        json.dump(track, f)
    return {"ok": True}


@app.get("/api/markup/{track_id}")
def get_markup(track_id: str):
    track = TRACKS.get(track_id)
    if not track:
        raise HTTPException(404, "Трек не найден")
    return {"markup": track.get("markup")}


@app.delete("/api/tracks/{track_id}")
def delete_track(track_id: str):
    track = TRACKS.pop(track_id, None)
    if not track:
        raise HTTPException(404, "Трек не найден")
    for p in {track.get("orig"), track.get("wav"), _meta_path(track_id)}:
        if p and os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass
    return {"ok": True}


@app.get("/api/analyze/{track_id}")
def analyze_track(track_id: str, n_segments: int | None = Query(None, ge=2, le=24)):
    track = TRACKS.get(track_id)
    if not track:
        raise HTTPException(404, "Трек не найден")
    result = analyze(track["wav"], n_segments=n_segments)
    result["track_id"] = track_id
    result["name"] = track["name"]
    return result


@app.get("/api/audio/{track_id}")
def get_audio(track_id: str):
    """Браузеру отдаём оригинальный (сжатый) файл — быстрее качается,
    decodeAudioData умеет mp3/ogg/flac и т.д."""
    track = TRACKS.get(track_id)
    if not track:
        raise HTTPException(404, "Трек не найден")
    return FileResponse(track["orig"], media_type=track["mime"])


@app.post("/api/loopability/{track_id}")
def loopability(track_id: str, segments: list[dict] = Body(...)):
    """Пересчитать качество лупа для отредактированных вручную границ."""
    track = TRACKS.get(track_id)
    if not track:
        raise HTTPException(404, "Трек не найден")
    return {"loopability": loop_quality(track["wav"], segments)}


@app.post("/api/export/{track_id}")
def export_loops(track_id: str, segments: list[dict] = Body(...)):
    """Нарезать трек на лупы по границам и вернуть zip с WAV-файлами.

    Режем оригинальный файл (полное качество, 44.1kHz stereo 16bit), а не
    моно-WAV для анализа. ZIP_STORED: PCM почти не сжимается deflate'ом,
    а времени на попытку уходит много.
    """
    track = TRACKS.get(track_id)
    if not track:
        raise HTTPException(404, "Трек не найден")
    if not segments:
        raise HTTPException(400, "Пустой список сегментов")

    import io
    import re
    import tempfile
    import zipfile
    import soundfile as sf

    # декодируем оригинал в полном качестве (единожды, ~1-2с на трек)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", track["orig"], "-ac", "2", "-ar", "44100",
             "-acodec", "pcm_s16le", tmp_path],
            check=True, capture_output=True,
        )
        y, sr = sf.read(tmp_path, always_2d=True, dtype="int16")
    except subprocess.CalledProcessError:
        raise HTTPException(500, "Не удалось декодировать оригинал (ffmpeg)")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        for i, s in enumerate(segments):
            a, b = int(float(s["start"]) * sr), int(float(s["end"]) * sr)
            a, b = max(0, a), min(len(y), b)
            if b - a < sr // 10:
                continue
            wav_io = io.BytesIO()
            sf.write(wav_io, y[a:b], sr, format="WAV", subtype="PCM_16")
            label = re.sub(r"[^\w\-]+", "_", str(s.get("label", f"part{i+1}")))
            zf.writestr(f"{i+1:02d}_{label}.wav", wav_io.getvalue())
    buf.seek(0)

    base = os.path.splitext(track["name"] or "loops")[0]
    from fastapi.responses import Response
    return Response(
        buf.read(), media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{base}_loops.zip"'},
    )


@app.get("/")
def index():
    """Отдаём прекомпилированную страницу (app.js), если она собрана и свежее
    исходника; иначе dev-версию с Babel в браузере (медленнее на слабых
    машинах/каналах). Пересборка: python3 tools/build.py"""
    prod = os.path.join(FRONTEND_DIR, "index.prod.html")
    dev = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(prod) and os.path.getmtime(prod) >= os.path.getmtime(dev):
        return FileResponse(prod, media_type="text/html")
    return FileResponse(dev, media_type="text/html")


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
