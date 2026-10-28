#!/usr/bin/env python3
from pathlib import Path
import shutil
import sys

if len(sys.argv) != 2:
    raise SystemExit(r"usage: python restore_moe_probe.py C:\path\to\llama.cpp")

root = Path(sys.argv[1]).resolve()
cuda_dir = root / "ggml" / "src" / "ggml-cuda"
target = cuda_dir / "ggml-cuda.cu"
backup = target.with_suffix(target.suffix + ".moe-probe.bak")

if backup.exists():
    shutil.copy2(backup, target)
    print("RESTORED:", target)
else:
    print("No backup found:", backup)

header = cuda_dir / "ram2vram-moe-probe.cuh"
if header.exists():
    header.unlink()
    print("REMOVED :", header)
