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


def main() -> None:
    audio, out_path = sys.argv[1], sys.argv[2]
    import allin1

    with tempfile.TemporaryDirectory() as tmp:
        result = allin1.analyze(
            audio, device="cuda", out_dir=os.path.join(tmp, "struct"),
            demix_dir=os.path.join(tmp, "demix"),
            spec_dir=os.path.join(tmp, "spec"),
            keep_byproducts=False,
        )

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
