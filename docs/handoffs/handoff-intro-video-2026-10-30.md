# Handoff: intro video, 2026-10-30

What changed: `video/` added (scenes, capture, narration, captions, `build.sh`, README); `/video/out/` gitignored. Branch `claude/intro-video-7bff02`, pushed. PR not opened (permission denied in the session), open it with:
`gh pr create --repo oguznacar10/aim-hackathon-ehds-oguz-arda --head claude/intro-video-7bff02 --base main --title "Intro video: 2-minute cut built from the app"`

Verified: `bash video/build.sh assemble`, ffprobe on `video/out/gatekeeper-intro.mp4`: h264, 1920x1080, 30/1, aac, duration 120.000000; blackdetect clean on both footage clips; no em-dash in `video/`.

Open: Engine section (0:40-1:05) is a plain title card until the model comparison numbers are final (swap the `s-03-engine` block in `video/scenes/index.html`, re-render with `node video/render.mjs 03-engine`, then `video/build.sh assemble`). Voice is macOS `say` (Samantha), segment 6 at rate 285 to fit 15 s; `video/narration.txt` has the six segments for a human recording. App footage shows app-native numbers (patient and record counts in the SPE notice). Capture must run against a server started with no API key in the environment, or the queue shows "LLM plan unusable: HTTP Error 401".

Next: Arda records narration, replaces `video/out/narration.wav` (120 s, 48 kHz stereo), runs `video/build.sh assemble`.
