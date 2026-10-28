#!/usr/bin/env python3
from pathlib import Path
import re, sys

if len(sys.argv) != 2:
    raise SystemExit(r"usage: python inspect_moe_path.py C:\path\to\llama.cpp")

root = Path(sys.argv[1]).resolve()
patterns = [
    ("GGML_OP_MUL_MAT_ID", re.compile(r"GGML_OP_MUL_MAT_ID")),
    ("ggml_cuda_mul_mat_id", re.compile(r"ggml_cuda_mul_mat_id")),
    ("mul_mat_id(", re.compile(r"\bmul_mat_id\s*\(")),
    ("mm_ids_helper", re.compile(r"mm_ids_helper")),
    ("TOPK_MOE", re.compile(r"TOPK_MOE")),
    ("ids->data", re.compile(r"ids\s*->\s*data")),
    ("dst->src[2]", re.compile(r"dst\s*->\s*src\s*\[\s*2\s*\]")),
]
exts={".cu",".cuh",".cpp",".cc",".c",".h",".hpp"}
hits=[]
for p in root.rglob("*"):
    if not p.is_file() or p.suffix.lower() not in exts: continue
    try: text=p.read_text(encoding="utf-8", errors="replace")
    except Exception: continue
    for label,rx in patterns:
        for m in rx.finditer(text):
            line=text.count("\n",0,m.start())+1
            hits.append((str(p.relative_to(root)),line,label))

print("=== MoE / MUL_MAT_ID source hits ===")
for file,line,label in sorted(hits):
    print(f"{file}:{line}: {label}")

interesting=[]
for file,line,label in hits:
    lf=file.lower().replace("\\","/")
    score=0
    if "ggml-cuda" in lf: score+=5
    if "compute-forward" in lf: score+=5
    if "/mmid." in lf or lf.endswith("/mmid.cu"): score+=8
    if "ggml-cuda.cu" in lf: score+=4
    if label=="ggml_cuda_mul_mat_id": score+=8
    if label=="GGML_OP_MUL_MAT_ID": score+=4
    interesting.append((score,file,line,label))
interesting.sort(reverse=True)

seen=set(); count=0
print("\n=== Top excerpts ===")
for score,file,line,label in interesting:
    key=(file,line//20)
    if key in seen: continue
    seen.add(key)
    p=root/file
    lines=p.read_text(encoding="utf-8",errors="replace").splitlines()
    a=max(1,line-12); b=min(len(lines),line+24)
    print(f"\n--- {file}:{line} [{label}] score={score} ---")
    for n in range(a,b+1):
        print(f"{n:5d}: {lines[n-1]}")
    count+=1
    if count>=8: break

print("\n=== Next ===")
print("Send back moe_path_report.txt. We will patch the exact current-source MoE path.")
