#!/usr/bin/env python3
"""Runner для SongFormer + Beat This! в отдельном venv.

Вызывается из backend/main.py как subprocess:
    .venv-songformer/bin/python tools/songformer_analyze.py input.mp3 output.json

Требует переменную SONGFORMER_SRC — путь к клону репозитория SongFormer
(его infer-код не упакован в pip). setup-ai-songformer.sh кладёт клон в
.venv-songformer/src и выставляет всё сам.

Выход — JSON с bpm, beats, downbeats, segments (start/end/label).
"""
import json
import os
import subprocess
import sys
import tempfile


def pick_device() -> str:
    import torch
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def run_beats(audio: str, device: str):
    """Beat This!: биты и downbeats; темп — из межбитовых интервалов."""
    import numpy as np
    from beat_this.inference import File2Beats
    # dbn=False — без madmom
    dev = device if device != "mps" else "cpu"  # у beat_this с mps бывают проблемы
    f2b = File2Beats(checkpoint_path="final0", device=dev, dbn=False)
    beats, downbeats = f2b(audio)
    beats = [float(b) for b in beats]
    downbeats = [float(b) for b in downbeats]
    if len(beats) > 3:
        bpm = float(60.0 / np.median(np.diff(beats)))
    else:
        bpm = 120.0
    return bpm, beats, downbeats


def run_structure(audio: str, src_dir: str, py: str):
    """SongFormer через официальный infer.py (subprocess внутри venv)."""
    sf_dir = os.path.join(src_dir, "src", "SongFormer")
    with tempfile.TemporaryDirectory() as tmp:
        scp = os.path.join(tmp, "in.scp")
        with open(scp, "w") as f:
            f.write(os.path.abspath(audio) + "\n")
        out_dir = os.path.join(tmp, "out")
        os.makedirs(out_dir, exist_ok=True)
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.join(src_dir, "src", "third_party") + ":" + sf_dir
        proc = subprocess.run(
            [py, os.path.join(sf_dir, "infer", "infer.py"),
             "-i", scp, "-o", out_dir,
             "--model", "SongFormer",
             "--checkpoint", "SongFormer.safetensors",
             "--config_path", "SongFormer.yaml",
             "-gn", "1", "-tn", "1"],
            cwd=sf_dir, env=env, capture_output=True, text=True, timeout=1800,
        )
        outs = [f for f in os.listdir(out_dir) if f.endswith(".json")]
        if not outs:
            sys.stderr.write(proc.stderr[-1500:] if proc.stderr else "no output")
            raise RuntimeError("SongFormer produced no output")
        with open(os.path.join(out_dir, outs[0])) as f:
            return json.load(f)


def main() -> None:
    audio, out_path = sys.argv[1], sys.argv[2]
    src_dir = os.environ.get("SONGFORMER_SRC")
    if not src_dir or not os.path.isdir(src_dir):
        sys.exit("SONGFORMER_SRC is not set or missing")

    device = pick_device()
    print(f"device: {device}", file=sys.stderr)

    raw_segments = run_structure(audio, src_dir, sys.executable)
    bpm, beats, downbeats = run_beats(audio, device)

    # SongFormer дробит секции на подсекции с одинаковым лейблом (по фразам) —
    # сливаем смежные одноимённые: для лупов нужны крупные части
    merged = []
    for s in raw_segments:
        if merged and merged[-1]["label"] == s["label"]:
            merged[-1]["end"] = float(s["end"])
        else:
            merged.append({"label": str(s["label"]),
                           "start": float(s["start"]), "end": float(s["end"])})

    data = {
        "bpm": bpm,
        "beats": beats,
        "downbeats": downbeats,
        "segments": merged,
        "segments_raw": [
            {"label": str(s["label"]), "start": float(s["start"]),
             "end": float(s["end"])} for s in raw_segments
        ],
    }
    with open(out_path, "w") as f:
        json.dump(data, f)
    print("OK")


if __name__ == "__main__":
    main()
