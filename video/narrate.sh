#!/bin/bash
# Renders the six narration.txt segments with macOS say, fits each to its slot, mixes out/narration.wav (120.000 s, 48 kHz stereo).
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p out/voice
VOICE=Samantha
starts=(0 15 40 65 90 105)
ends=(15 40 65 90 105 120)
inputs=()
filter=""
printf "%-8s %-6s %-7s %s\n" segment slot spoken rate
for i in 1 2 3 4 5 6; do
  text=$(awk -v n="[$i]" '$1==n{f=1;next} f&&/^\[/{f=0} f&&NF{print}' narration.txt)
  slot=$(( ends[i-1] - starts[i-1] ))
  rate=175
  while :; do
    say -v "$VOICE" -r "$rate" -o "out/voice/seg$i.aiff" "$text"
    ffmpeg -y -loglevel error -i "out/voice/seg$i.aiff" -ar 48000 -ac 2 "out/voice/seg$i.wav"
    dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "out/voice/seg$i.wav")
    if python3 -c "import sys; sys.exit(0 if $dur <= $slot - 0.5 else 1)" || [ "$rate" -ge 300 ]; then break; fi
    rate=$(( rate + 10 > 300 ? 300 : rate + 10 ))
  done
  printf "%-8s %-6s %-7.2f %s\n" "$i" "$slot" "$dur" "$rate"
  inputs+=(-i "out/voice/seg$i.wav")
  filter+="[$((i-1))]adelay=$(( starts[i-1] * 1000 )):all=1[a$i];"
done
filter+="[a1][a2][a3][a4][a5][a6]amix=inputs=6:normalize=0,apad[out]"
ffmpeg -y -loglevel error "${inputs[@]}" -filter_complex "$filter" -map "[out]" -ar 48000 -ac 2 -c:a pcm_s16le -t 120 out/narration.wav
ffprobe -v error -show_entries format=duration -show_entries stream=sample_rate,channels -of default=nw=1 out/narration.wav
