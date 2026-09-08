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

from .analysis import analyze, analyze_deep_merge, loop_quality

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# Python из venv c allin1 (torch+NATTEN). Приоритет: env-переменная ->
# локальный .venv-ai (создаётся ./setup-ai.sh) -> путь на dev-сервере.
def _find_deep_py() -> str | None:
    cands = [
        os.environ.get("MUSSLOP_DEEP_PY"),
        os.path.join(BASE_DIR, ".venv-ai", "bin", "python"),
        "/workspace-SR008.fs2/mikheev-kandy/.envs/allin1/bin/python",
    ]
    for c in cands:
        if c and os.path.exists(c):
            return c
    return None


DEEP_PY = _find_deep_py()
DEEP_AVAILABLE = DEEP_PY is not None

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
    return {"status": "ok", "tracks": len(TRACKS), "deep_available": DEEP_AVAILABLE}


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
            "favorite": bool(m.get("favorite")),
            "duration": (m.get("markup") or {}).get("duration"),
            "n_segments": len((m.get("markup") or {}).get("segments", []) or []),
        })
    # библиотека сверху, внутри групп — по свежести
    items.sort(key=lambda x: (not x["favorite"], -x["uploaded_at"]))
    return {"tracks": items}


@app.post("/api/favorite/{track_id}")
def toggle_favorite(track_id: str, body: dict = Body(...)):
    """Добавить/убрать трек из библиотеки (favorite=true/false)."""
    track = TRACKS.get(track_id)
    if not track:
        raise HTTPException(404, "Трек не найден")
    track["favorite"] = bool(body.get("favorite"))
    with open(_meta_path(track_id), "w") as f:
        json.dump(track, f)
    return {"ok": True, "favorite": track["favorite"]}


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
def analyze_track(track_id: str,
                  n_segments: int | None = Query(None, ge=2, le=24),
                  engine: str = Query("fast")):
    track = TRACKS.get(track_id)
    if not track:
        raise HTTPException(404, "Трек не найден")

    if engine == "deep":
        if not DEEP_AVAILABLE:
            raise HTTPException(503, "Глубокий анализ недоступен (venv allin1 не найден)")
        result = _deep_analyze(track)
    else:
        result = analyze(track["wav"], n_segments=n_segments)

    result["track_id"] = track_id
    result["name"] = track["name"]
    return result


def _deep_analyze(track: dict) -> dict:
    """allin1 в отдельном venv (subprocess), результат кэшируется в meta."""
    cached = track.get("deep_raw")
    if not cached:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            out_json = tmp.name
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        try:
            proc = subprocess.run(
                [DEEP_PY, os.path.join(base, "tools", "deep_analyze.py"),
                 track["orig"], out_json],
                capture_output=True, text=True, timeout=1800,
            )
            if proc.returncode != 0:
                tail = (proc.stderr or "")[-800:]
                raise HTTPException(500, f"Ошибка глубокого анализа: {tail}")
            with open(out_json) as f:
                cached = json.load(f)
        finally:
            if os.path.exists(out_json):
                os.remove(out_json)
        track["deep_raw"] = cached
        with open(_meta_path(track["id"]), "w") as f:
            json.dump(track, f)
    return analyze_deep_merge(track["wav"], cached)


@app.get("/api/audio/{track_id}")
def get_audio(track_id: str, transcode: int = Query(0)):
    """Браузеру отдаём оригинальный (сжатый) файл — быстрее качается.
    ?transcode=1 — перекодировать в WAV 44.1kHz stereo: нужен, когда
    decodeAudioData не осиливает оригинал (например, FLAC с обложкой
    декодируется не полностью)."""
    track = TRACKS.get(track_id)
    if not track:
        raise HTTPException(404, "Трек не найден")
    if transcode:
        safe = track.get("safe_wav")
        if not safe or not os.path.exists(safe):
            safe = os.path.join(UPLOAD_DIR, f"{track_id}.playback.wav")
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-vn", "-i", track["orig"],
                     "-ac", "2", "-ar", "44100", "-acodec", "pcm_s16le", safe],
                    check=True, capture_output=True,
                )
            except subprocess.CalledProcessError:
                raise HTTPException(500, "Не удалось перекодировать (ffmpeg)")
            track["safe_wav"] = safe
            with open(_meta_path(track_id), "w") as f:
                json.dump(track, f)
        return FileResponse(safe, media_type="audio/wav")
    return FileResponse(track["orig"], media_type=track["mime"])


@app.post("/api/loopability/{track_id}")
def loopability(track_id: str, segments: list[dict] = Body(...)):
    """Пересчитать качество лупа для отредактированных вручную границ."""
    track = TRACKS.get(track_id)
    if not track:
        raise HTTPException(404, "Трек не найден")
    return {"loopability": loop_quality(track["wav"], segments)}


STEM_NAMES = ("drums", "bass", "other", "vocals")
STEM_JOBS: dict[str, dict] = {}  # track_id -> {"status", "progress", "error"}


def _stems_done(stem_dir: str) -> bool:
    return all(os.path.exists(os.path.join(stem_dir, f"{n}.wav"))
               for n in STEM_NAMES)


def _run_demix(track_id: str, orig: str, stem_dir: str) -> None:
    """Фоновая задача: demucs с парсингом прогресса из stderr."""
    import re as _re
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    job = STEM_JOBS[track_id]
    try:
        proc = subprocess.Popen(
            [DEEP_PY, os.path.join(base, "tools", "demix.py"), orig, stem_dir],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
        )
        # demucs обновляет прогресс-бар через \r — читаем посимвольно
        buf = ""
        while True:
            ch = proc.stderr.read(1)
            if ch == "" and proc.poll() is not None:
                break
            if ch in ("\r", "\n"):
                m = _re.search(r"(\d+)%\|", buf)
                if m:
                    job["progress"] = int(m.group(1))
                buf = ""
            else:
                buf += ch
        proc.wait(timeout=3600)
        if proc.returncode != 0 or not _stems_done(stem_dir):
            job["status"] = "error"
            job["error"] = "Разделение не удалось (см. server.log)"
            return
        track = TRACKS.get(track_id)
        if track is not None:
            track["stems"] = stem_dir
            with open(_meta_path(track_id), "w") as f:
                json.dump(track, f)
        job["status"] = "done"
        job["progress"] = 100
    except Exception as e:  # noqa: BLE001
        job["status"] = "error"
        job["error"] = str(e)[:300]


@app.post("/api/stems/{track_id}")
def make_stems(track_id: str):
    """Запустить разделение на стемы (фон). Статус — GET /api/stems/{id}/status."""
    track = TRACKS.get(track_id)
    if not track:
        raise HTTPException(404, "Трек не найден")
    if not DEEP_AVAILABLE:
        raise HTTPException(503, "Стемы недоступны: нет ИИ-окружения (./setup-ai.sh)")

    stem_dir = os.path.join(UPLOAD_DIR, f"{track_id}.stems")
    if _stems_done(stem_dir):
        STEM_JOBS[track_id] = {"status": "done", "progress": 100, "error": None}
        return {"ok": True, "status": "done", "stems": list(STEM_NAMES)}

    job = STEM_JOBS.get(track_id)
    if job and job.get("status") == "running":
        return {"ok": True, "status": "running", "progress": job.get("progress", 0)}

    STEM_JOBS[track_id] = {"status": "running", "progress": 0, "error": None}
    import threading
    threading.Thread(target=_run_demix, args=(track_id, track["orig"], stem_dir),
                     daemon=True).start()
    return {"ok": True, "status": "running", "progress": 0}


@app.get("/api/stems/{track_id}/status")
def stems_status(track_id: str):
    stem_dir = os.path.join(UPLOAD_DIR, f"{track_id}.stems")
    if _stems_done(stem_dir):
        return {"status": "done", "progress": 100}
    job = STEM_JOBS.get(track_id)
    if not job:
        return {"status": "none", "progress": 0}
    return {"status": job["status"], "progress": job.get("progress", 0),
            "error": job.get("error")}


@app.get("/api/stems/{track_id}/{stem}")
def get_stem(track_id: str, stem: str):
    if stem not in STEM_NAMES:
        raise HTTPException(404, "Нет такого стема")
    path = os.path.join(UPLOAD_DIR, f"{track_id}.stems", f"{stem}.wav")
    if not os.path.exists(path):
        raise HTTPException(404, "Стем не готов")
    return FileResponse(path, media_type="audio/wav")


@app.post("/api/import_url")
def import_url(body: dict = Body(...)):
    """Импорт трека по ссылке (YouTube и всё, что умеет yt-dlp)."""
    url = (body.get("url") or "").strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "Некорректная ссылка")

    track_id = uuid.uuid4().hex[:12]
    out_tpl = os.path.join(UPLOAD_DIR, f"{track_id}.%(ext)s")
    proc = subprocess.run(
        [os.sys.executable, "-m", "yt_dlp", "-x", "--audio-format", "mp3",
         "--audio-quality", "0", "--no-playlist", "--max-filesize", "200M",
         "-o", out_tpl, "--print", "after_move:filepath",
         "--print", "title", url],
        capture_output=True, text=True, timeout=600,
    )
    if proc.returncode != 0:
        raise HTTPException(400, f"Не удалось скачать: {(proc.stderr or '')[-400:]}")
    lines = [l for l in proc.stdout.strip().splitlines() if l.strip()]
    title = lines[0] if lines else "track"
    orig_path = os.path.join(UPLOAD_DIR, f"{track_id}.mp3")
    if not os.path.exists(orig_path):
        raise HTTPException(500, "Файл не появился после скачивания")

    wav_path = os.path.join(UPLOAD_DIR, f"{track_id}.analysis.wav")
    try:
        _to_wav(orig_path, wav_path)
    except subprocess.CalledProcessError:
        os.remove(orig_path)
        raise HTTPException(400, "Не удалось декодировать скачанное аудио")

    meta = {"id": track_id, "orig": orig_path, "wav": wav_path,
            "name": f"{title}.mp3", "mime": "audio/mpeg",
            "uploaded_at": int(__import__("time").time())}
    TRACKS[track_id] = meta
    with open(_meta_path(track_id), "w") as f:
        json.dump(meta, f)
    return {"track_id": track_id, "name": meta["name"]}


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
