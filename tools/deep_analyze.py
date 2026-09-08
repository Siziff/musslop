#!/usr/bin/env python3
"""Runner для allin1 в отдельном venv (torch/NATTEN несовместимы с базовым питоном).

Вызывается из backend/main.py как subprocess:
    .envs/allin1/bin/python tools/deep_analyze.py input.mp3 output.json

Выход — JSON с beats, downbeats, segments (start/end/label), bpm.
"""
import json
import os
import sys
import tempfile


def pick_device() -> str:
    """cuda -> cpu. MPS намеренно пропущен: NATTEN (ядро allin1) не
    поддерживает MPS — на Apple Silicon работаем на CPU."""
    import torch
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def main() -> None:
    audio, out_path = sys.argv[1], sys.argv[2]
    import allin1

    device = pick_device()
    print(f"device: {device}", file=sys.stderr)

    def run(dev):
        with tempfile.TemporaryDirectory() as tmp:
            return allin1.analyze(
                audio, device=dev, out_dir=os.path.join(tmp, "struct"),
                demix_dir=os.path.join(tmp, "demix"),
                spec_dir=os.path.join(tmp, "spec"),
                keep_byproducts=False,
            )

    try:
        result = run(device)
    except Exception as e:
        # NATTEN на macOS собирается CPU-only: MPS может не поддерживаться
        if device != "cpu":
            print(f"{device} failed ({e}), retrying on cpu", file=sys.stderr)
            result = run("cpu")
        else:
            raise

    segments = [
        {"start": float(s.start), "end": float(s.end), "label": str(s.label)}
        for s in result.segments
    ]
    data = {
        "bpm": float(result.bpm),
        "beats": [float(b) for b in result.beats],
        "downbeats": [float(b) for b in result.downbeats],
        "segments": segments,
    }
    with open(out_path, "w") as f:
        json.dump(data, f)
    print("OK")


if __name__ == "__main__":
    main()
