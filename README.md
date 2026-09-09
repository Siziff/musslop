<p align="center">
  <img src="assets/banner.png" alt="musslop — adaptive game-style loops from any track" width="100%">
</p>

<h3 align="center">Any track becomes a game soundtrack</h3>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.10+-d8ff3e?style=flat-square&labelColor=111" alt="Python 3.10+"></a>
  <a href="https://fastapi.tiangolo.com/"><img src="https://img.shields.io/badge/FastAPI%20%2B%20librosa-backend-d8ff3e?style=flat-square&labelColor=111" alt="FastAPI + librosa backend"></a>
  <a href="https://developer.mozilla.org/docs/Web/API/Web_Audio_API"><img src="https://img.shields.io/badge/React%20%2B%20Web%20Audio-frontend-d8ff3e?style=flat-square&labelColor=111" alt="React + Web Audio frontend"></a>
  <a href="https://github.com/ASLP-lab/SongFormer"><img src="https://img.shields.io/badge/SongFormer-neural%20analysis-d8ff3e?style=flat-square&labelColor=111" alt="SongFormer neural analysis"></a>
  <a href="https://github.com/mir-aidj/all-in-one"><img src="https://img.shields.io/badge/All--In--One-neural%20analysis-d8ff3e?style=flat-square&labelColor=111" alt="All-In-One neural analysis"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-d8ff3e?style=flat-square&labelColor=111" alt="MIT license"></a>
</p>

<p align="center">
  <b>Loop any section forever · hit «Next» · the music evolves — seamlessly, on the beat</b>
</p>

---

In games, music *reacts*: stay in the tavern and its theme loops forever; descend into
the dungeon and the score darkens with you. **musslop** does this with any mp3.

Drop a track → AI finds the musical structure → every section becomes a perfect loop →
you drive the music live, like a game audio engine — no editing skills required.

<p align="center">
  <img src="assets/demo.gif" alt="musslop demo: loop plays, press Next, seamless transition" width="85%">
</p>

## Why it feels magic

| | |
|---|---|
| 🧠 **AI structure analysis** | two neural engines find sections *and name them* (Intro, Verse, Chorus, Solo): [SongFormer](https://github.com/ASLP-lab/SongFormer) (2025, faster, best on pop/rock/electronic) and [All-In-One](https://github.com/mir-aidj/all-in-one) (2023, steadier on orchestral); beats/downbeats via [Beat This!](https://github.com/CPJKU/beat_this). Fast heuristic fallback (~2 s) works everywhere |
| 🔁 **Seamless loops** | sample-accurate Web Audio scheduling, bar-snapped boundaries, per-section loop-quality score (⟳%), equal-power crossfades |
| 🎚 **Intensity layers** | Demucs splits the track into drums / bass / vocals / backing — toggle and mix layers live: calm exploration → full combat, same track |
| 🎬 **Pro transitions** | post-exit tails ring out over the next section, bass-swap keeps exactly one bassline at any moment, one-shot stingers (cymbal / boom / riser) punctuate scene changes |
| 📈 **Knows what not to loop** | build-ups are detected by their crescendo shape and play once, as dramatic bridges |
| ✂️ **Full editor** | drag boundaries with bar snapping, split/merge, loop-start markers, Ctrl+Z, zoom + scrollbar, everything auto-saved |

## Built for the game table 🎲

The flagship use case is **tabletop RPG**: turn any track into a *location theme*.
The party lingers in the tavern — the tavern section loops. They open the dungeon door —
one keypress, and the music descends with them, on the beat, mid-session.
There is even a **Tavern UI theme** (wood, parchment & gold) switchable in the header.

Also great for: game dev prototyping (audition adaptive behaviour before wiring
FMOD/Wwise, export loop WAVs), streaming, practice looping, focus music.

## Quick start

```bash
pip install -r requirements.txt   # ffmpeg must be in PATH
./run.sh                          # → http://localhost:8801
```

**Optional AI engines** (each is one command, both auto-detected by `run.sh`):

```bash
./setup-ai-songformer.sh  # SongFormer 2025 + Beat This! — newer, faster,
                          # best on pop/rock/electronic; plain pip, no compilers
./setup-ai-allin1.sh      # All-In-One 2023 + Demucs — steadier on orchestral,
                          # also powers the stem "layers" feature
```

Works fully offline after setup. First AI analysis of a track: ~1 min on GPU,
a few minutes on CPU; results are cached — reopening is instant.

## Under the hood

1. **Beat & downbeat tracking** — onset envelope + dynamic programming (Ellis 2007)
2. **Structure** — neural (All-In-One, WASPAA 2023) or Foote novelty on
   beat-synced chroma+MFCC+RMS self-similarity
3. **Loop-aware refinement** — boundaries move along downbeats maximizing loop
   closure quality (head/tail spectral similarity), phrase lengths (4/8 bars) and
   transition audibility
4. **Build-up detection** — normalized RMS slope + trend R² + spectral-centroid rise
5. **Playback** — every loop pass is an independent `AudioBufferSourceNode`;
   transitions land on loop/phrase boundaries with micro-fades, tails and bass-swap

Built on the shoulders of: [SongFormer](https://github.com/ASLP-lab/SongFormer) (ASLP-lab, CC-BY-4.0) ·
[All-In-One](https://github.com/mir-aidj/all-in-one) (Kim & Nam, MIT) ·
[Beat This!](https://github.com/CPJKU/beat_this) (CPJKU, MIT) ·
[Demucs](https://github.com/facebookresearch/demucs) · [librosa](https://librosa.org) —
plus classic MIR: Ellis 2007 (beat tracking), Foote 2000 (novelty segmentation).

## API

| Endpoint | Purpose |
|---|---|
| `POST /api/upload` · `POST /api/import_url` | file upload / yt-dlp import |
| `GET /api/analyze/{id}?engine=fast\|deep` | structure analysis |
| `POST /api/stems/{id}` · `GET /api/stems/{id}/{stem}` | Demucs 4-stem split |
| `POST /api/export/{id}` | zip of full-quality loop WAVs |
| `GET/POST /api/markup/{id}` | segment markup persistence |
| `GET /api/tracks` · `POST /api/favorite/{id}` | history & library |

## Troubleshooting

1. `curl http://localhost:8801/api/health` → expect `{"status":"ok", ...}`
2. Blank page → hard-refresh (`Ctrl+F5`), check browser console (`F12`)
3. Port busy → `./run.sh` frees it; manually: `lsof -ti tcp:8801 | xargs kill`
4. No sound → click the ♪? self-test in the volume box (bottom-right)
5. Server errors → `server.log`
