# itch.io — publishing kit for musslop

Everything for **Dashboard → Create new project**. Files in this folder are ready to upload;
the field values below can be pasted as-is.

## Form fields

| Field | Value |
|---|---|
| **Title** | musslop — adaptive music loops for TTRPG sessions & game prototypes |
| **Project URL** | `siziff.itch.io/musslop` (or whatever is free) |
| **Short description / tagline** | Loop any section of a track and cue the next one when the scene calls for it. Free, open source, runs locally. |
| **Classification** | Tools |
| **Kind of project** | Downloadable |
| **Release status** | Released (or *In development* if you prefer to signal active work) |
| **Pricing** | No payments — *keep it free; "pay what you want" would contradict the "free forever" message* |
| **Uploads** | Two files: `musslop-source.zip` (repo archive from GitHub, mark **Windows · macOS · Linux**) + a text file `INSTALL.txt` with the 4 commands. When a packaged build exists, add it as a separate upload. |
| **Genre** | — (leave empty; it's a tool) |
| **Tags** (max 10) | `music`, `audio`, `tool`, `tabletop`, `dungeons-and-dragons`, `game-audio`, `adaptive-music`, `open-source`, `loop`, `soundtrack` |
| **AI generation disclosure** | *Yes* → note: "AI assistance was used for parts of the UI code. No generated music or assets; optional pretrained models analyse the user's own tracks." |
| **App store links** | GitHub: `https://github.com/Siziff/musslop` |
| **Community** | Comments enabled |
| **Visibility** | Public |

## Images

| Slot | File | Notes |
|---|---|---|
| Cover image (630×500) | `cover-630x500.png` | rendered at 2× (1260×1000) — itch downsizes it |
| Screenshots | `shot-1-editor.png` — waveform editor & parts<br>`shot-2-scenes-player.png` — scenes + queued transition<br>`shot-3-live.png` — Live mode desk<br>`shot-4-tavern.png` — Tavern theme | upload in this order |
| Trailer (YouTube/Vimeo URL) | upload `demo_classic_zoom.mp4` to YouTube as *unlisted*, paste the link | optional but strongly recommended |

## Theme (Edit theme)

Background `#111419` · text `#f7f7ef` · links/buttons `#d8ff3e` · button text `#111419`.
Font: default sans. Banner: none (cover is enough).

## Description (paste into the rich-text editor; it accepts this HTML)

```html
<p><strong>The boss finishes their speech. Your players reach for their dice. This is where the music should kick in…</strong> and instead the track slides into a quiet interlude.</p>

<p><strong>musslop</strong> turns any music track into game-style loops. Pick a section and it repeats for as long as the scene needs. Press <strong>Next</strong> — or the key of any part — and the music moves on <em>at a musical boundary</em>, not mid-bar.</p>

<h3>For tabletop sessions</h3>
<ul>
<li><strong>Loop any section</strong> of your existing music (mp3, wav, flac…). Automatic structure analysis finds intro / verse / chorus; you can drag the boundaries.</li>
<li><strong>Cue transitions</strong> into any part: <em>natural</em> (loop end), <em>soon</em> (next phrase), <em>now</em> (short crossfade). Cancel if the players change their mind.</li>
<li><strong>Scenes</strong> — save "Empty corridor", "Something is close", "Ambush", "Aftermath" from one track, with hotkeys.</li>
<li><strong>Live mode</strong> — a full-screen desk with big buttons, what's playing, what's next and when. Fade out in one key.</li>
<li><strong>Projects</strong> — a set list for the whole session: groups of tracks and scenes with notes.</li>
<li>Optional <strong>intensity layers</strong>: split a track into drums / bass / vocals / backing and mix them live.</li>
</ul>

<h3>For game developers</h3>
<ul>
<li>Audition how a linear track behaves as interactive music before writing stems or wiring FMOD/Wwise.</li>
<li>Check a loop seam or a transition in six seconds instead of listening to a whole pass.</li>
<li><strong>Export WAV loops + <code>manifest.json</code></strong> with loop points, phrase transition points, tails, stingers and scenes. A Godot 4 example script is included.</li>
</ul>

<h3>Free. Open source. Yours.</h3>
<p>MIT license. No accounts, subscriptions, registration or e-mail. Runs on your computer and works offline once installed. This is a personal project I built for my own table and decided to share.</p>

<h3>Install (Windows / macOS / Linux)</h3>
<p>Needs <a href="https://python.org">Python 3.10+</a> and Git.</p>
<pre>git clone https://github.com/Siziff/musslop.git
cd musslop
./setup.sh     # Windows: setup.bat
./run.sh       # Windows: run.bat  →  http://localhost:8801</pre>
<p>ffmpeg is downloaded automatically. Neural analysis (SongFormer / All-In-One) and layer separation (Demucs) are optional one-command add-ons described in the README.</p>

<p><strong>Source & issues:</strong> <a href="https://github.com/Siziff/musslop">github.com/Siziff/musslop</a> — a ⭐ helps other people find it.<br>
<strong>How it works</strong> (beat tracking, novelty segmentation, loop-closure refinement, Web Audio scheduling): <a href="https://habr.com/ru/articles/1086674/">article</a>.</p>

<p><em>Results depend on the track: automatic boundaries are a starting point, and the editor is there for a reason. Bring your own music — musslop doesn't generate any.</em></p>
```

## INSTALL.txt (upload as a second file)

```
musslop — install
=================
Requires Python 3.10+ (python.org, tick "Add to PATH" on Windows) and Git.

Linux / macOS:
  git clone https://github.com/Siziff/musslop.git && cd musslop
  ./setup.sh
  ./run.sh          → open http://localhost:8801

Windows:
  git clone https://github.com/Siziff/musslop.git
  cd musslop
  setup.bat
  run.bat           → open http://localhost:8801

Optional AI engines: ./setup-ai-songformer.sh (all platforms), ./setup-ai-allin1.sh (Linux/macOS/WSL).
Docs & issues: https://github.com/Siziff/musslop
```

## First devlog (post right after publishing — devlogs show up in feeds)

**Title:** musslop 0.1 — loop any track like a game soundtrack

> First public release. What's in: automatic section analysis (heuristic + optional SongFormer / All-In-One), sample-accurate loops in the browser, cue transitions into any part (natural / soon / now), scenes with hotkeys, Live mode for running a session, projects (set lists), WAV + manifest export with a Godot example.
>
> What I'd love feedback on: how well the automatic boundaries work on *your* music (orchestral is the hardest), and whether the Live desk is usable behind a DM screen. Comments open.

## After publishing

- Add the itch page link to the GitHub README (badge or a line under Quick start).
- Post the page to the itch **community → Tools** board once; later use devlogs for updates (each devlog = a new appearance in followers' feeds).
- When a packaged build exists, upload it as a separate file and mark platforms — that's when itch traffic really converts.
