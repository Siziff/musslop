#!/usr/bin/env python3
"""Оценка и тюнинг авто-нарезки по ручным разметкам.

Использование:
  1. Разметь треки в UI и сохрани разметку (кнопка "⤓ Разметка").
  2. Сложи пары в каталог examples/:
       examples/track1.mp3
       examples/track1.musslop.json   (имя = имя трека + .musslop.json)
  3. Оценка текущего алгоритма:
       python3 tools/tune.py examples/
     Подбор весов _boundary_score (grid search):
       python3 tools/tune.py examples/ --search

Метрика: F-мера попадания границ с допуском +-1 такт (и +-0.5 c для справки).
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np  # noqa: E402


def load_pairs(directory: str) -> list[tuple[str, list[float]]]:
    """[(audio_path, [границы в сек, без 0 и конца])]."""
    pairs = []
    for fn in sorted(os.listdir(directory)):
        if not fn.endswith(".musslop.json"):
            continue
        meta = json.load(open(os.path.join(directory, fn)))
        base = fn[: -len(".musslop.json")]
        audio = None
        for ext in (".mp3", ".wav", ".ogg", ".flac", ".m4a"):
            p = os.path.join(directory, base + ext)
            if os.path.exists(p):
                audio = p
                break
        if audio is None:
            print(f"!! нет аудио для {fn}")
            continue
        segs = sorted(meta["segments"], key=lambda s: s["start"])
        bounds = [float(s["start"]) for s in segs[1:]]  # внутренние границы
        pairs.append((audio, bounds))
    return pairs


def f_measure(pred: list[float], true: list[float], tol: float) -> tuple[float, float, float]:
    if not pred and not true:
        return 1.0, 1.0, 1.0
    if not pred or not true:
        return 0.0, 0.0, 0.0
    matched_t = set()
    tp = 0
    for p in pred:
        best, bd = None, tol
        for i, t in enumerate(true):
            if i in matched_t:
                continue
            d = abs(p - t)
            if d <= bd:
                bd, best = d, i
        if best is not None:
            matched_t.add(best)
            tp += 1
    prec = tp / len(pred)
    rec = tp / len(true)
    f = 2 * prec * rec / max(prec + rec, 1e-9)
    return f, prec, rec


def evaluate(pairs, weights=None) -> dict:
    from backend import analysis as A

    if weights is not None:
        A.BOUNDARY_WEIGHTS.update(weights)

    rows, fs = [], []
    for audio, true_bounds in pairs:
        r = A.analyze(audio)
        pred = [s["start"] for s in r["segments"][1:]]
        bar = 60.0 / max(r["tempo"], 1e-6) * 4
        f_bar, p, rc = f_measure(pred, true_bounds, tol=bar)
        f_05, _, _ = f_measure(pred, true_bounds, tol=0.5)
        rows.append((os.path.basename(audio), f_bar, f_05, p, rc,
                     len(pred), len(true_bounds)))
        fs.append(f_bar)
    return {"rows": rows, "mean_f": float(np.mean(fs)) if fs else 0.0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("directory", help="каталог с парами трек+разметка")
    ap.add_argument("--search", action="store_true", help="grid search весов")
    args = ap.parse_args()

    pairs = load_pairs(args.directory)
    if not pairs:
        print("Пары не найдены. Нужны файлы вида track.mp3 + track.musslop.json")
        return
    print(f"Найдено пар: {len(pairs)}")

    res = evaluate(pairs)
    print("\n=== Текущий алгоритм ===")
    for name, fb, f05, p, r, np_, nt in res["rows"]:
        print(f"  {name:40s} F(+-1 такт)={fb:.2f} F(+-0.5с)={f05:.2f} "
              f"P={p:.2f} R={r:.2f} pred={np_} true={nt}")
    print(f"  mean F = {res['mean_f']:.3f}")

    if not args.search:
        return

    print("\n=== Grid search весов границы ===")
    grid = {
        "loop_q": [0.2, 0.3, 0.4],
        "phrase": [0.1, 0.2, 0.3],
        "audib": [0.1, 0.2, 0.3],
        "novelty": [0.2, 0.3, 0.4],
    }
    best = (res["mean_f"], None)
    keys = list(grid)
    for combo in itertools.product(*(grid[k] for k in keys)):
        w = dict(zip(keys, combo))
        r = evaluate(pairs, weights=w)
        if r["mean_f"] > best[0]:
            best = (r["mean_f"], dict(w))
            print(f"  new best F={best[0]:.3f}  {best[1]}")
    print(f"\nЛучшее: F={best[0]:.3f}, веса: {best[1] or 'дефолтные'}")
    if best[1]:
        print("Чтобы применить, обнови BOUNDARY_WEIGHTS в backend/analysis.py")


if __name__ == "__main__":
    main()
