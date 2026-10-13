#!/bin/sh
# Start the PrismML llama.cpp router: one endpoint, three models, chosen per request.
#   http://127.0.0.1:8888          web UI (pick the model in the UI; needs the API key)
#   http://127.0.0.1:8888/v1/...   OpenAI-compatible API, "model": "<section in models.ini>"
# Localhost only. After 10 min idle the loaded model sleeps: its memory is freed
# (~0.1 GiB left) and the next request wakes it, ~2-20 s depending on model and cache.
set -eu
P="$(cd "$(dirname "$0")" && pwd)"
cd "$P"   # model paths in models.ini are relative to this directory
exec "$P/bin/current/llama-server" \
  --host 127.0.0.1 --port 8888 \
  --models-preset "$P/models.ini" \
  --models-max 1 \
  --api-key-file "$P/secrets/api-key.txt" \
  --sleep-idle-seconds 600 \
  "$@"
