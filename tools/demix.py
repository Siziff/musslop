#!/usr/bin/env python3
"""Разделение трека на 4 стема (drums/bass/vocals/other) через Demucs.

Запускается в venv allin1 (там уже стоит demucs как зависимость):
    .envs/allin1/bin/python tools/demix.py input.mp3 output_dir/

Пишет в output_dir: drums.wav, bass.wav, vocals.wav, other.wav (44.1k stereo).
"""
import os
import sys


def pick_device() -> str:
    import torch
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def main() -> None:
    audio, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)

    import subprocess
    import tempfile

    import numpy as np
    import soundfile as sf
    import torch
    from demucs.apply import apply_model
    from demucs.pretrained import get_model
    from demucs.audio import save_audio

    device = pick_device()
    print(f"device: {device}", file=sys.stderr)

    model = get_model("htdemucs")
    model.to(device).eval()

    # читаем аудио сами (demucs.AudioFile требует ffprobe, которого может не быть):
    # mp3/flac -> временный wav через ffmpeg, wav читаем soundfile
    src_path = audio
    tmp_wav = None
    if not audio.lower().endswith(".wav"):
        tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
        subprocess.run(["ffmpeg", "-y", "-vn", "-i", audio, "-ac", "2",
                        "-ar", str(model.samplerate), tmp_wav],
                       check=True, capture_output=True)
        src_path = tmp_wav
    try:
        data, sr = sf.read(src_path, always_2d=True, dtype="float32")
        if sr != model.samplerate:
            # простая ресэмплировка через ffmpeg уже сделана выше для не-wav;
            # для wav с другим sr — конвертируем тоже
            tmp2 = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
            subprocess.run(["ffmpeg", "-y", "-i", src_path, "-ac", "2",
                            "-ar", str(model.samplerate), tmp2],
                           check=True, capture_output=True)
            data, sr = sf.read(tmp2, always_2d=True, dtype="float32")
            os.remove(tmp2)
        if data.shape[1] == 1:
            data = np.repeat(data, 2, axis=1)
        wav = torch.from_numpy(data.T.copy())  # (channels, samples)
    finally:
        if tmp_wav and os.path.exists(tmp_wav):
            os.remove(tmp_wav)

    ref = wav.mean(0)
    wav = (wav - ref.mean()) / (ref.std() + 1e-8)

    with torch.no_grad():
        sources = apply_model(model, wav[None], device=device, split=True,
                              overlap=0.15, progress=True)[0]
    sources = sources * (ref.std() + 1e-8) + ref.mean()

    for name, src in zip(model.sources, sources):
        save_audio(src.cpu(), os.path.join(out_dir, f"{name}.wav"),
                   samplerate=model.samplerate)
    print("OK")


if __name__ == "__main__":
    main()
