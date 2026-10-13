#!/bin/sh
# Install the PrismML llama.cpp fork (prebuilt macOS arm64 release), pinned + SHA256-checked,
# into bin/<release>/ and point bin/current at it. Idempotent.
set -eu
P="$(cd "$(dirname "$0")" && pwd)"
REL=prism-b10735-842b188
TAR=llama-$REL-bin-macos-arm64.tar.gz
SHA=a5c7a4d1f4f4ac7571aefdda5d1861e92ae196588dabb92525265d4c4ccbb7bb   # = GitHub's asset digest
URL=https://github.com/PrismML-Eng/llama.cpp/releases/download/$REL/$TAR

if [ -x "$P/bin/llama-$REL/llama-server" ]; then
  echo "[ok]   runtime $REL already installed"
else
  mkdir -p "$P/downloads" "$P/bin"
  if [ ! -f "$P/downloads/$TAR" ] || [ "$(shasum -a 256 "$P/downloads/$TAR" | cut -d' ' -f1)" != "$SHA" ]; then
    echo "[get]  $TAR"
    curl -fL --retry 3 -o "$P/downloads/$TAR.part" "$URL"
    got=$(shasum -a 256 "$P/downloads/$TAR.part" | cut -d' ' -f1)
    [ "$got" = "$SHA" ] || { echo "[FAIL] sha256 $got != $SHA"; exit 1; }
    mv "$P/downloads/$TAR.part" "$P/downloads/$TAR"
  fi
  tar xzf "$P/downloads/$TAR" -C "$P/bin"          # -> bin/llama-$REL/
  echo "[ok]   runtime $REL installed"
fi
ln -sfn "llama-$REL" "$P/bin/current"
"$P/bin/current/llama-server" --version 2>&1 | grep -m1 -i version || true
