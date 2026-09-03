# Musslop — анализ аудио: биты, такты, структурная сегментация.
#
# Теория, на которой основана нарезка:
#  1. Beat tracking: огибающая онсетов + динамическое программирование (Ellis, 2007).
#  2. Downbeats: предполагаем размер 4/4; фаза сильной доли выбирается как
#     сдвиг (0..3), максимизирующий среднюю силу онсета на каждом 4-м бите.
#  3. Структурная сегментация (Foote, 2000): beat-синхронные признаки
#     (CQT-хрома — гармония, MFCC — тембр) -> матрица самоподобия ->
#     свёртка "шахматным" ядром по диагонали -> кривая новизны ->
#     пики = границы секций (интро/куплет/припев/бридж...).
#  4. Музыкальное квантование: границы притягиваются к ближайшему downbeat,
#     минимальная длина секции — 4 такта (типичная музыкальная фраза).

from __future__ import annotations

import numpy as np
import scipy.signal
import scipy.ndimage
import librosa

SR = 22050
HOP = 512


def _checkerboard_kernel(size: int) -> np.ndarray:
    """Гауссово-взвешенное шахматное ядро Фута (size — половина стороны)."""
    n = 2 * size
    g = scipy.signal.windows.gaussian(n, std=size / 2.0)
    kernel = np.outer(g, g)
    sign = np.ones((n, n))
    sign[:size, size:] = -1
    sign[size:, :size] = -1
    return kernel * sign


def _novelty_from_ssm(ssm: np.ndarray, kernel_size: int) -> np.ndarray:
    """Кривая новизны: свёртка SSM шахматным ядром вдоль главной диагонали."""
    n = ssm.shape[0]
    ks = min(kernel_size, max(4, n // 4))
    kernel = _checkerboard_kernel(ks)
    pad = ks
    padded = np.pad(ssm, pad, mode="edge")
    novelty = np.zeros(n)
    for i in range(n):
        window = padded[i : i + 2 * ks, i : i + 2 * ks]
        novelty[i] = np.sum(window * kernel)
    novelty = np.maximum(novelty, 0.0)
    if novelty.max() > 0:
        novelty /= novelty.max()
    return novelty


def _estimate_downbeat_phase(onset_env: np.ndarray, beat_frames: np.ndarray,
                             beats_per_bar: int = 4) -> int:
    """Фаза сильной доли: сдвиг, при котором онсеты на битах сильнее всего."""
    if len(beat_frames) < beats_per_bar:
        return 0
    strengths = onset_env[np.clip(beat_frames, 0, len(onset_env) - 1)]
    scores = [strengths[p::beats_per_bar].mean() for p in range(beats_per_bar)]
    return int(np.argmax(scores))


def _snap(value: float, grid: np.ndarray) -> float:
    """Ближайшая точка сетки."""
    if len(grid) == 0:
        return value
    return float(grid[np.argmin(np.abs(grid - value))])


def analyze(path: str, n_segments: int | None = None) -> dict:
    """Полный анализ трека. Возвращает dict для JSON-ответа."""
    y, sr = librosa.load(path, sr=SR, mono=True)
    duration = float(len(y) / sr)

    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP)
    tempo, beat_frames = librosa.beat.beat_track(
        onset_envelope=onset_env, sr=sr, hop_length=HOP, trim=False
    )
    tempo = float(np.atleast_1d(tempo)[0])
    beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=HOP)

    # --- Downbeats (такты, размер 4/4) -------------------------------------
    beats_per_bar = 4
    phase = _estimate_downbeat_phase(onset_env, beat_frames, beats_per_bar)
    downbeat_times = beat_times[phase::beats_per_bar]

    if len(beat_times) < 16:
        # fallback: равномерная нарезка, если ритм не найден
        n = n_segments or max(2, int(duration // 20))
        bounds = np.linspace(0, duration, n + 1)
        segments = [
            {"start": float(bounds[i]), "end": float(bounds[i + 1]),
             "label": f"Часть {i + 1}"}
            for i in range(n)
        ]
        return {
            "duration": duration,
            "tempo": tempo,
            "beats": beat_times.tolist(),
            "downbeats": downbeat_times.tolist(),
            "segments": segments,
            "fallback": True,
        }

    # --- Beat-синхронные признаки: гармония + тембр + энергия ---------------
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=HOP)
    mfcc = librosa.feature.mfcc(y=y, sr=sr, hop_length=HOP, n_mfcc=13)
    mfcc = mfcc[1:]  # без 0-го коэффициента (громкость)
    rms = librosa.feature.rms(y=y, hop_length=HOP)  # огибающая громкости

    sync_frames = librosa.util.fix_frames(beat_frames, x_min=0,
                                          x_max=chroma.shape[1] - 1)
    chroma_sync = librosa.util.sync(chroma, sync_frames, aggregate=np.median)
    mfcc_sync = librosa.util.sync(mfcc, sync_frames, aggregate=np.mean)
    rms_sync = librosa.util.sync(rms, sync_frames, aggregate=np.mean)

    def _norm(f):
        f = f - f.mean(axis=1, keepdims=True)
        s = f.std(axis=1, keepdims=True)
        return f / np.maximum(s, 1e-8)

    feats = np.vstack([
        _norm(chroma_sync) * 1.0,   # гармония
        _norm(mfcc_sync) * 0.7,     # тембр
        _norm(rms_sync) * 2.0,      # динамика (вход/уход инструментов)
    ])
    feats = librosa.util.normalize(feats, axis=0)

    # --- SSM + новизна ------------------------------------------------------
    ssm = np.dot(feats.T, feats)
    ssm = scipy.ndimage.median_filter(ssm, size=(3, 3))

    n_beats = ssm.shape[0]
    kernel_beats = 4 * beats_per_bar  # окно контекста: 4 такта в каждую сторону
    novelty = _novelty_from_ssm(ssm, kernel_beats)
    novelty = scipy.ndimage.gaussian_filter1d(novelty, sigma=2)

    min_gap_beats = 4 * beats_per_bar  # секция не короче 4 тактов
    peaks, props = scipy.signal.find_peaks(
        novelty, distance=min_gap_beats, prominence=0.05
    )

    if n_segments is not None and len(peaks) > n_segments - 1:
        order = np.argsort(props["prominences"])[::-1][: n_segments - 1]
        peaks = np.sort(peaks[order])
    elif n_segments is None and len(peaks) > 11:
        order = np.argsort(props["prominences"])[::-1][:11]
        peaks = np.sort(peaks[order])

    sync_times = librosa.frames_to_time(sync_frames, sr=sr, hop_length=HOP)
    bound_times = [sync_times[p] for p in peaks if p < len(sync_times)]

    # --- Квантование границ к downbeats + уточнение -------------------------
    # Пик новизны размыт (ядро на 4 такта), поэтому ближайший downbeat может
    # промахиваться на такт. Уточняем: среди downbeats в окне +-1 такт вокруг
    # кандидата выбираем тот, где переход "слышнее" всего:
    #   * сильный онсет на самой границе (вступление новой партии),
    #   * максимальный скачок RMS-энергии между тактом до и тактом после.
    grid = downbeat_times if len(downbeat_times) > 2 else beat_times
    onset_times = librosa.times_like(onset_env, sr=sr, hop_length=HOP)
    rms_env = rms[0]
    rms_times = librosa.times_like(rms_env, sr=sr, hop_length=HOP)
    bar_dur = (60.0 / max(tempo, 1e-6)) * beats_per_bar

    onset_n = onset_env / max(onset_env.max(), 1e-8)

    def _onset_at(t: float) -> float:
        i = int(np.argmin(np.abs(onset_times - t)))
        lo, hi = max(0, i - 2), min(len(onset_n), i + 3)
        return float(onset_n[lo:hi].max())

    def _rms_jump(t: float) -> float:
        """|среднее RMS такта после - такта до| (нормированное)."""
        pre = rms_env[(rms_times >= t - bar_dur) & (rms_times < t)]
        post = rms_env[(rms_times >= t) & (rms_times < t + bar_dur)]
        if len(pre) == 0 or len(post) == 0:
            return 0.0
        denom = max(float(rms_env.mean()), 1e-8)
        return abs(float(post.mean()) - float(pre.mean())) / denom

    def _refine(t: float) -> float:
        cands = grid[np.abs(grid - t) <= bar_dur * 1.05]
        if len(cands) == 0:
            return _snap(t, grid)
        best, best_score = float(cands[0]), -1.0
        for c in cands:
            c = float(c)
            # штраф за удаление от пика новизны, чтобы не уползать без причины
            dist_pen = abs(c - t) / bar_dur * 0.15
            score = 0.6 * _onset_at(c) + 0.4 * min(_rms_jump(c), 2.0) - dist_pen
            if score > best_score:
                best_score, best = score, c
        return best

    snapped = sorted({_refine(t) for t in bound_times})

    min_len = max(4.0, (60.0 / max(tempo, 1e-6)) * beats_per_bar * 2)  # >= 2 тактов
    bounds = [0.0]
    for t in snapped:
        if t - bounds[-1] >= min_len and duration - t >= min_len:
            bounds.append(float(t))
    bounds.append(duration)

    # --- Добор до запрошенного числа частей ---------------------------------
    # Если пиков новизны не хватило, делим самые длинные части по downbeat,
    # ближайшему к локальному максимуму новизны внутри части.
    if n_segments is not None:
        def _novelty_at(t: float) -> float:
            i = int(np.argmin(np.abs(sync_times - t)))
            return float(novelty[i])

        while len(bounds) - 1 < n_segments:
            best = None  # (novelty, split_time, insert_pos)
            for i in range(len(bounds) - 1):
                lo, hi = bounds[i] + min_len, bounds[i + 1] - min_len
                if hi <= lo:
                    continue
                cands = grid[(grid >= lo) & (grid <= hi)]
                for c in cands:
                    score = _novelty_at(float(c))
                    if best is None or score > best[0]:
                        best = (score, float(c), i + 1)
            if best is None:
                break  # физически некуда делить (min_len)
            bounds.insert(best[2], best[1])

    segments = [
        {"start": bounds[i], "end": bounds[i + 1], "label": f"Часть {i + 1}"}
        for i in range(len(bounds) - 1)
    ]

    # --- Автолейблы: кластеризация похожих секций (A/B/A/C -> куплет/припев) -
    _label_segments(segments, feats, sync_times)

    # --- Качество лупа: насколько бесшовно зациклится каждая часть ----------
    for s in segments:
        s["loopability"] = _loopability(y, sr, s["start"], s["end"])

    return {
        "duration": duration,
        "tempo": tempo,
        "beats": beat_times.tolist(),
        "downbeats": downbeat_times.tolist(),
        "segments": segments,
        "fallback": False,
    }


def _label_segments(segments: list, feats: np.ndarray,
                    sync_times: np.ndarray) -> None:
    """Помечает похожие секции одной буквой (A, B, C...) через агломеративную
    кластеризацию усреднённых beat-признаков сегмента."""
    n = len(segments)
    if n == 0:
        return
    vecs = []
    for s in segments:
        mask = (sync_times >= s["start"]) & (sync_times < s["end"])
        v = feats[:, mask].mean(axis=1) if mask.any() else feats.mean(axis=1)
        nrm = np.linalg.norm(v)
        vecs.append(v / max(nrm, 1e-8))
    vecs = np.array(vecs)

    if n == 1:
        segments[0]["group"] = "A"
        segments[0]["label"] = "A1"
        return

    from scipy.cluster.hierarchy import linkage, fcluster
    from scipy.spatial.distance import pdist
    d = pdist(vecs, metric="cosine")
    z = linkage(d, method="average")
    # порог: близкие по звучанию секции считаем «той же» частью
    labels = fcluster(z, t=0.45, criterion="distance")

    # буквы в порядке первого появления
    order: dict[int, str] = {}
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    counts: dict[str, int] = {}
    for seg, lab in zip(segments, labels):
        if lab not in order:
            order[lab] = letters[len(order) % len(letters)]
        g = order[lab]
        counts[g] = counts.get(g, 0) + 1
        seg["group"] = g
        seg["label"] = f"{g}{counts[g]}"


def loop_quality(path: str, segments: list) -> list:
    """Качество лупа для готового списка границ (для ручного редактирования)."""
    y, sr = librosa.load(path, sr=SR, mono=True)
    return [_loopability(y, sr, float(s["start"]), float(s["end"]))
            for s in segments]


def _loopability(y: np.ndarray, sr: int, start: float, end: float,
                 win: float = 0.5) -> float:
    """Оценка бесшовности лупа 0..1: похожи ли крайние полсекунды по спектру
    и нет ли резкого разрыва громкости на стыке конец->начало."""
    i0, i1 = int(start * sr), int(end * sr)
    w = int(win * sr)
    if i1 - i0 < 4 * w:
        return 0.5
    head = y[i0:i0 + w]
    tail = y[i1 - w:i1]

    # спектральная похожесть хвоста и головы (mel-спектр, косинус)
    def _spec(x):
        s = librosa.feature.melspectrogram(y=x, sr=sr, n_mels=48, hop_length=HOP)
        v = np.log1p(s).mean(axis=1)
        return v / max(np.linalg.norm(v), 1e-8)

    sim = float(np.dot(_spec(head), _spec(tail)))  # 0..1

    # разрыв громкости на стыке
    rh = float(np.sqrt(np.mean(head ** 2)) + 1e-8)
    rt = float(np.sqrt(np.mean(tail ** 2)) + 1e-8)
    level = min(rh, rt) / max(rh, rt)  # 1 = уровни равны

    return float(np.clip(0.7 * sim + 0.3 * level, 0.0, 1.0))
