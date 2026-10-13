#!/bin/sh
# Whisper GGML models for whisper.cpp, pinned to a Hugging Face revision and SHA256-checked.
#   ggml-large-v3-turbo.bin  1.62 GB  (default: ~ same quality, much faster)
#   (ggml-large-v3.bin 3.10 GB, the full model, was removed 2026-09-25: slower AND worse
#    than turbo in tests/eval.py; its line below is commented out)
#   ggml-silero-v6.2.0.bin   0.9 MB   (VAD: skips non-speech before whisper; ggml-org/whisper-vad)
set -eu
D="$(cd "$(dirname "$0")" && pwd)/models"
REPO=ggerganov/whisper.cpp
REV=5359861c739e955e79d9a303bcbc70fb988958b1
mkdir -p "$D"

get() {  # file sha256 [repo] [rev]
  f="$D/$1"; repo="${3:-$REPO}"; rev="${4:-$REV}"
  if [ -f "$f" ] && [ "$(shasum -a 256 "$f" | cut -d' ' -f1)" = "$2" ]; then
    echo "ok (already present): $1"; return
  fi
  curl -fL --retry 3 -C - -o "$f.part" "https://huggingface.co/$repo/resolve/$rev/$1"
  got="$(shasum -a 256 "$f.part" | cut -d' ' -f1)"
  [ "$got" = "$2" ] || { echo "SHA256 MISMATCH for $1: $got" >&2; exit 1; }
  mv "$f.part" "$f"; echo "ok: $1"
}

get ggml-large-v3-turbo.bin 1fc70f774d38eb169993ac391eea357ef47c88757ef72ee5943879b7e8e2bc69
# get ggml-large-v3.bin       64d182b440b98d5203c4f9bd541544d84c605196c4f7b845dfa11fb23594d1e2
get ggml-silero-v6.2.0.bin   2aa269b785eeb53a82983a20501ddf7c1d9c48e33ab63a41391ac6c9f7fb6987 ggml-org/whisper-vad 9ffd54a1e1ee413ddf265af9913beaf518d1639b
