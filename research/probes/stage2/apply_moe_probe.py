#!/usr/bin/env python3
from pathlib import Path
import shutil
import sys

if len(sys.argv) != 2:
    raise SystemExit(r"usage: python apply_moe_probe.py C:\path\to\llama.cpp")

root = Path(sys.argv[1]).resolve()
cuda_dir = root / "ggml" / "src" / "ggml-cuda"
target = cuda_dir / "ggml-cuda.cu"

if not target.exists():
    raise SystemExit("ERROR: ggml-cuda.cu not found")

header_src = Path(__file__).with_name("ram2vram-moe-probe.cuh")
header_dst = cuda_dir / header_src.name
shutil.copy2(header_src, header_dst)

text = target.read_text(encoding="utf-8", errors="replace")

backup = target.with_suffix(target.suffix + ".moe-probe.bak")
if not backup.exists():
    shutil.copy2(target, backup)

include = '#include "ram2vram-moe-probe.cuh"'
if include not in text:
    lines = text.splitlines(True)
    last_inc = -1
    for i, line in enumerate(lines):
        if line.lstrip().startswith("#include"):
            last_inc = i
    if last_inc < 0:
        raise SystemExit("ERROR: include block not found")
    lines.insert(last_inc + 1, include + "\n")
    text = "".join(lines)

signature = "static void ggml_cuda_mul_mat_id(ggml_backend_cuda_context & ctx, ggml_tensor * dst) {"
pos = text.find(signature)
if pos < 0:
    raise SystemExit("ERROR: expected ggml_cuda_mul_mat_id signature not found")

locals_marker = "    GGML_TENSOR_BINARY_OP_LOCALS"
locals_pos = text.find(locals_marker, pos)
if locals_pos < 0 or locals_pos > pos + 3000:
    raise SystemExit("ERROR: GGML_TENSOR_BINARY_OP_LOCALS not found in ggml_cuda_mul_mat_id")

line_end = text.find("\n", locals_pos)
if line_end < 0:
    raise SystemExit("ERROR: malformed source around locals marker")

probe_call = """
    // RAM2VRAM MoE locality probe. Must run before MMVQ/MMVF fast-path returns.
    ram2vram_probe_moe_ids(ctx, src0, src1, ids, dst);
"""

if "ram2vram_probe_moe_ids(ctx, src0, src1, ids, dst);" not in text:
    text = text[:line_end+1] + probe_call + text[line_end+1:]

target.write_text(text, encoding="utf-8")

print("PATCHED :", target)
print("HEADER  :", header_dst)
print("BACKUP  :", backup)
print()
print("Verify:")
print(r'findstr /N /C:"ram2vram_probe_moe_ids" C:\path\to\llama.cpp\ggml\src\ggml-cuda\ggml-cuda.cu')
