#!/usr/bin/env python3
"""Runner for allin1 in a separate venv (torch/NATTEN are incompatible with the base python).

Called from backend/main.py as a subprocess:
    .envs/allin1/bin/python tools/deep_analyze.py input.mp3 output.json

Output - JSON with beats, downbeats, segments (start/end/label), bpm.
"""
import json
import os
import sys
import tempfile


def pick_device() -> str:
    """cuda -> cpu. MPS is skipped on purpose: NATTEN (the allin1 core) does
    not support MPS - on Apple Silicon we run on CPU."""
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
        # NATTEN on macOS builds CPU-only: MPS may be unsupported
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
