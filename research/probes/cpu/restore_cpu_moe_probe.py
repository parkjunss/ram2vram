#!/usr/bin/env python3
from pathlib import Path
import shutil, sys
if len(sys.argv) != 2:
    raise SystemExit(r"usage: python restore_cpu_moe_probe.py C:\path\to\llama.cpp")
root = Path(sys.argv[1]).resolve()
target = root / "ggml" / "src" / "ggml-cpu" / "ggml-cpu.c"
backup = target.with_suffix(target.suffix + ".moe-probe.bak")
if not backup.exists():
    raise SystemExit("ERROR: backup not found")
shutil.copy2(backup, target)
print("RESTORED:", target)
