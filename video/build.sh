#!/usr/bin/env bash
# Builds video/out/gatekeeper-intro.mp4 (1920x1080, 30 fps, H.264, 120 s).
# Needs: ffmpeg, node with playwright, macOS say, the app served at 127.0.0.1:8765
# (python3 scripts/serve.py --port 8765). Steps can be skipped with: build.sh assemble
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=video/out
mkdir -p "$OUT/seg" "$OUT/captions"

step="${1:-all}"
run() { [[ "$step" == all || "$step" == "$1" ]]; }

run scenes   && node video/render.mjs
run capture  && node video/capture.mjs
run narrate  && bash video/narrate.sh
run captions && node video/captions.mjs

if run assemble; then
  for f in 01-intro 02-applicant 03-engine 04-staff 05-federated 06-results 07-vision; do
    [[ -f "$OUT/seg/$f.mp4" ]] || { echo "missing $OUT/seg/$f.mp4"; exit 1; }
  done
  printf "file '%s'\n" 01-intro.mp4 02-applicant.mp4 03-engine.mp4 04-staff.mp4 05-federated.mp4 06-results.mp4 07-vision.mp4 > "$OUT/seg/list.txt"
  ffmpeg -y -hide_banner -loglevel error -f concat -safe 0 -i "$OUT/seg/list.txt" -c:v libx264 -pix_fmt yuv420p -preset veryfast -crf 18 -r 30 -an "$OUT/picture.mp4"

  # One overlay per caption cue, switched on only inside its time window.
  python3 - "$OUT" <<'PY'
import json, sys
out = sys.argv[1]
cues = json.load(open(f"{out}/captions/cues.json"))
inputs = "".join(f" -i {out}/captions/{c['file']}" for c in cues)
chain, prev = [], "[0:v]"
for i, c in enumerate(cues, 1):
    lab = f"[v{i}]"
    chain.append(f"{prev}[{i}:v]overlay=0:0:enable='between(t,{c['start']:.3f},{c['end']:.3f})'{lab}")
    prev = lab
open(f"{out}/overlay.args", "w").write(inputs.strip() + "\n")
open(f"{out}/overlay.filter", "w").write(";".join(chain) + "\n")
open(f"{out}/overlay.last", "w").write(prev + "\n")
PY
  N=$(python3 -c "import json,sys; print(len(json.load(open('$OUT/captions/cues.json'))))")
  # shellcheck disable=SC2046
  ffmpeg -y -hide_banner -loglevel error -i "$OUT/picture.mp4" $(cat "$OUT/overlay.args") -i "$OUT/narration.wav" \
    -filter_complex_script "$OUT/overlay.filter" -map "$(cat "$OUT/overlay.last")" -map "$((N + 1)):a" \
    -c:v libx264 -pix_fmt yuv420p -preset medium -crf 18 -r 30 -c:a aac -b:a 160k -t 120 "$OUT/gatekeeper-intro.mp4"
  ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate:format=duration -of default=nw=1 "$OUT/gatekeeper-intro.mp4"
fi
