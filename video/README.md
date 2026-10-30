# Intro video

Two-minute intro for .Gatekeeper, built from the app itself.

- `scenes/index.html` + `render.mjs`: animated title and diagram scenes, rendered frame by frame with Playwright.
- `capture.mjs`: real app footage (Applicant and Staff views) recorded against `127.0.0.1:8765`.
- `narrate.sh`: placeholder voice with macOS `say`; `narration.txt` has the six segments and timings for a human recording.
- `captions/` + `captions.mjs`: caption overlays rendered as PNGs (ffmpeg here has no drawtext).
- `build.sh`: runs the steps and assembles `out/gatekeeper-intro.mp4` (1920x1080, 30 fps, H.264, 120 s).

Run: `python3 scripts/serve.py --port 8765` in one terminal, then `video/build.sh` (or `video/build.sh assemble` to re-mux only). Output under `video/out/` is gitignored.
