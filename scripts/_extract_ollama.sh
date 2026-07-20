#!/usr/bin/env bash
# Extract the ollama .tar.zst without a system zstd binary (uses pip zstandard).
set -uo pipefail
cd ~/ollama

if [ -f bin/ollama ]; then echo "already extracted"; exit 0; fi
[ -f ollama.tar.zst ] || { echo "ollama.tar.zst missing"; exit 1; }

python3 -m pip install --break-system-packages -q zstandard 2>&1 | tail -1 || true

echo "decompressing .zst -> .tar (python zstandard)..."
python3 - <<'PY'
import zstandard, pathlib
src = pathlib.Path.home() / "ollama" / "ollama.tar.zst"
dst = pathlib.Path.home() / "ollama" / "ollama.tar"
with open(src, "rb") as f, open(dst, "wb") as o:
    zstandard.ZstdDecompressor().copy_stream(f, o)
print("wrote", dst, dst.stat().st_size // (1024*1024), "MB")
PY

echo "untarring..."
tar -xf ollama.tar
rm -f ollama.tar ollama.tar.zst
./bin/ollama --version 2>&1 | head -2 || true
echo "OLLAMA_EXTRACTED"
