#!/bin/sh
# End-to-end setup on a Mac that has nothing but Homebrew. Safe to re-run: every step
# checks what is already there (downloads are pinned and SHA256-verified).
#
#   ./setup.sh                  # everything: runtime, bonsai + qwen + bielik (~37 GB), whisper
#   ./setup.sh bonsai           # only the LLMs you name (bonsai|qwen|bielik); whisper always
#
# Installs via brew: whisper.cpp ffmpeg yt-dlp (+ python if python3 is missing).
# Everything else stays inside this directory (gitignored): bin/, models/, secrets/.
set -eu
R="$(cd "$(dirname "$0")" && pwd)"
say() { printf '\n== %s\n' "$*"; }

say "platform"
[ "$(uname -s)" = Darwin ] && [ "$(uname -m)" = arm64 ] || { echo "needs macOS on Apple Silicon"; exit 1; }
echo "[ok]   macOS $(sw_vers -productVersion) arm64, $(sysctl -n hw.memsize | awk '{printf "%d GB", $1/1073741824}') RAM"
command -v brew >/dev/null || { echo "[FAIL] Homebrew not found: https://brew.sh"; exit 1; }
echo "[ok]   brew $(brew --version | head -1 | cut -d' ' -f2)"
free_gb=$(df -g "$R" | awk 'NR==2{print $4}')
echo "[info] ${free_gb} GB free on disk (full setup needs ~40 GB)"

say "brew packages"
for f in whisper.cpp ffmpeg yt-dlp; do
  if brew list --formula "$f" >/dev/null 2>&1; then echo "[ok]   $f $(brew list --versions "$f" | cut -d' ' -f2)"
  else echo "[get]  $f"; brew install "$f"; fi
done
if python3 -c 'import sys; assert sys.version_info >= (3, 9)' >/dev/null 2>&1; then
  echo "[ok]   python3 $(python3 -c 'import platform; print(platform.python_version())')"
else echo "[get]  python"; brew install python; fi
if command -v docker >/dev/null && docker info >/dev/null 2>&1; then echo "[ok]   docker (used only by the LLM quality eval sandbox)"
else echo "[info] docker not running -- optional, only llama-cpp-prism/quality/ needs it"; fi

say "llama.cpp runtime (PrismML fork)"
"$R/llama-cpp-prism/install_runtime.sh"

say "LLM models"
"$R/llama-cpp-prism/download_models.sh" "$@"

say "router API key"
K="$R/llama-cpp-prism/secrets/api-key.txt"
if [ -s "$K" ]; then echo "[ok]   $K exists (not shown)"
else
  (umask 077; mkdir -p "$(dirname "$K")"; printf 'sk-prism-%s\n' "$(openssl rand -hex 22)" > "$K")
  echo "[ok]   generated $K (0600, not shown)"
fi
chmod 700 "$(dirname "$K")"; chmod 600 "$K"

say "whisper models"
"$R/whisper/download_models.sh" | grep -E '^(ok|SHA)'

say "done"
cat <<EOF
LLMs:     $R/llama-cpp-prism/run.sh        -> http://127.0.0.1:8888 (web UI + OpenAI API)
Speech:   $R/whisper/transcribe.sh <youtube-url|file> [lang]
EOF
