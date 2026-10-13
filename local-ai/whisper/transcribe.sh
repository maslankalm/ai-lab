#!/bin/sh
# Transcribe a YouTube URL (or a local audio/video file) with whisper.cpp.
#
#   ./transcribe.sh <url|file> [auto|en|pl|...]
#
# Output: transcripts/<name>/{audio.wav, <model>.txt, <model>.srt}
# Model: whisper large-v3-turbo. Defaults: language auto-detect (pass pl/en to force it), Silero VAD on
# (skips non-speech; stops invented intro credits). VAD=0 turns it off -> turbo-novad.*
set -eu
H="$(cd "$(dirname "$0")" && pwd)"
SRC="${1:?usage: transcribe.sh <url|file> [lang]}"
LANG_="${2:-auto}"
MODEL=turbo
M="$H/models/ggml-large-v3-turbo.bin"

if [ -f "$SRC" ]; then
  NAME="$(basename "${SRC%.*}")"; OUT="$H/transcripts/$NAME"; mkdir -p "$OUT"
  [ -f "$OUT/audio.wav" ] || ffmpeg -nostdin -loglevel error -i "$SRC" -ar 16000 -ac 1 -c:a pcm_s16le "$OUT/audio.wav"
else
  NAME="$(yt-dlp --no-warnings --print id "$SRC")"; OUT="$H/transcripts/$NAME"; mkdir -p "$OUT"
  if [ ! -f "$OUT/audio.wav" ]; then
    yt-dlp --no-warnings -q -f bestaudio -o "$OUT/source.%(ext)s" --print-to-file title "$OUT/title.txt" "$SRC"
    ffmpeg -nostdin -loglevel error -i "$OUT"/source.* -ar 16000 -ac 1 -c:a pcm_s16le "$OUT/audio.wav"
    rm -f "$OUT"/source.*
  fi
fi

DUR="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT/audio.wav")"
if [ "${VAD:-1}" = 1 ]; then TAG="$MODEL"; set -- --vad -vm "$H/models/ggml-silero-v6.2.0.bin"
else TAG="$MODEL-novad"; set --; fi
T0=$(date +%s)
whisper-cli -m "$M" -f "$OUT/audio.wav" -l "$LANG_" -t 8 "$@" -otxt -osrt -of "$OUT/$TAG" > "$OUT/$TAG.log" 2>&1 \
  || { tail -20 "$OUT/$TAG.log" >&2; exit 1; }
T=$(( $(date +%s) - T0 ))
awk -v d="$DUR" -v t="$T" -v m="$TAG" -v o="$OUT" 'BEGIN{
  printf "%s: %.1f min audio in %d s (%.1fx real time) -> %s/%s.txt\n", m, d/60, t, d/(t>0?t:1), o, m }'
