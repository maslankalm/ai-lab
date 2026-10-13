#!/bin/sh
# Fetch the router's models into models/, each pinned to a Hugging Face revision and
# SHA256-checked (existing files are re-verified, not re-downloaded). Idempotent.
#
#   ./download_models.sh                    # all: bonsai qwen bielik  (~37 GB)
#   ./download_models.sh bonsai qwen
#
#   bonsai  Ternary-Bonsai-2-27B-PQ2_0.gguf       7.2 GB  (PrismML; needs the fork)
#   qwen    Qwen3.8-27B-UD-Q4_K_XL.gguf         17.6 GB  (Unsloth) + mmproj-F16 0.9 GB (vision)
#   bielik  Bielik-11B-v3.0-Instruct.Q8_0.gguf  11.9 GB  (SpeakLeash, Polish)
#
# PTQ1_0 (same Bonsai weights, 5.9 GB) was dropped 2026-09-25: ~14% slower than PQ2_0 on
# Metal. It is the faster packing on CUDA -- see the commented line below.
set -eu
D="$(cd "$(dirname "$0")" && pwd)/models"
mkdir -p "$D"

get() {  # repo rev remote-file sha256 [local-name]
  f="$D/${5:-$3}"
  if [ -f "$f" ] && [ "$(shasum -a 256 "$f" | cut -d' ' -f1)" = "$4" ]; then
    echo "[ok]   ${5:-$3} verified"; return 0
  fi
  echo "[get]  ${5:-$3}"
  curl -fL -C - --retry 5 --retry-delay 5 -o "$f.part" "https://huggingface.co/$1/resolve/$2/$3"
  got=$(shasum -a 256 "$f.part" | cut -d' ' -f1)
  [ "$got" = "$4" ] || { echo "[FAIL] ${5:-$3}: sha256 $got != $4"; exit 1; }
  mv "$f.part" "$f"; echo "[ok]   ${5:-$3} verified"
}

BONSAI="prism-ml/Ternary-Bonsai-2-27B-gguf 8b7157531df3859ce2a415c60754e9152554e25d"
QWEN="unsloth/Qwen3.8-27B-GGUF 4ca720788d1e01f1bff70c033e0d0028fd02e502"
BIELIK="speakleash/Bielik-11B-v3.0-Instruct-GGUF 518fbbc2e677bf490776e4a98a300a822faca1a2"

for m in ${*:-bonsai qwen bielik}; do
  case "$m" in
    bonsai)
      get $BONSAI Ternary-Bonsai-2-27B-PQ2_0.gguf 3907dc1658db1f78a9826bf8d5bcb8dc65db0d466388937af57f2294fae62ec1
      # get $BONSAI Ternary-Bonsai-2-27B-PTQ1_0.gguf 53107f530aa52eb00912263ab1ee29bd199261c87cd7b4ad4ca1318c1fe33ee3
      ;;
    qwen)
      get $QWEN Qwen3.8-27B-UD-Q4_K_XL.gguf 3f227079003add2511437e5b1e94812e363385225bf6a9b47b0054a72bc8b01e
      get $QWEN mmproj-F16.gguf cbb841a9ee0636b2ec172f5bb8df2ea8dfeb01e90fe7c6126581d662a0b4e43e Qwen3.8-27B-mmproj-F16.gguf
      ;;
    bielik)
      get $BIELIK Bielik-11B-v3.0-Instruct.Q8_0.gguf b2b1b8cd2056638d83a257c1fc20e334e0129195e8aa41c878fef6f56f1e6724
      ;;
    *) echo "unknown model '$m' (bonsai|qwen|bielik)" >&2; exit 2 ;;
  esac
done
