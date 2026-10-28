#!/usr/bin/env python3
"""
Inspect GGUF tensor metadata and estimate per-(layer, expert) bundle bytes for
gpt-oss style MoE tensors:

  blk.N.ffn_gate_exps.weight
  blk.N.ffn_up_exps.weight
  blk.N.ffn_down_exps.weight

Supports one GGUF, multiple GGUF shards, a directory, or glob patterns.
Uses on-disk tensor spans (offset -> next offset), which may include only tiny
alignment padding and is sufficiently accurate for VRAM/PCIe budgeting.
"""

from __future__ import annotations
import argparse
import glob
import json
import os
import re
import struct
from pathlib import Path
from typing import BinaryIO

GGUF_MAGIC = b"GGUF"

# GGUF metadata value types.
UINT8, INT8, UINT16, INT16, UINT32, INT32, FLOAT32, BOOL, STRING, ARRAY, UINT64, INT64, FLOAT64 = range(13)

def read_exact(f: BinaryIO, n: int) -> bytes:
    b = f.read(n)
    if len(b) != n:
        raise EOFError(f"unexpected EOF (wanted {n}, got {len(b)})")
    return b

def u32(f): return struct.unpack("<I", read_exact(f, 4))[0]
def u64(f): return struct.unpack("<Q", read_exact(f, 8))[0]

def gguf_string(f: BinaryIO) -> str:
    n = u64(f)
    return read_exact(f, n).decode("utf-8", errors="replace")

def skip_scalar(f: BinaryIO, typ: int):
    sizes = {
        UINT8: 1, INT8: 1, UINT16: 2, INT16: 2,
        UINT32: 4, INT32: 4, FLOAT32: 4, BOOL: 1,
        UINT64: 8, INT64: 8, FLOAT64: 8,
    }
    if typ in sizes:
        f.seek(sizes[typ], 1)
    elif typ == STRING:
        n = u64(f)
        f.seek(n, 1)
    elif typ == ARRAY:
        elem_type = u32(f)
        n = u64(f)
        for _ in range(n):
            skip_scalar(f, elem_type)
    else:
        raise ValueError(f"unsupported GGUF metadata type {typ}")

def read_metadata_value(f: BinaryIO, typ: int):
    # Read only simple values useful to us; skip everything else.
    if typ == UINT32:
        return u32(f)
    if typ == UINT64:
        return u64(f)
    if typ == STRING:
        return gguf_string(f)
    skip_scalar(f, typ)
    return None

def align_up(x: int, a: int) -> int:
    return (x + a - 1) // a * a

def parse_gguf(path: Path):
    with path.open("rb") as f:
        if read_exact(f, 4) != GGUF_MAGIC:
            raise ValueError(f"{path}: not a GGUF file")
        version = u32(f)
        n_tensors = u64(f)
        n_kv = u64(f)

        alignment = 32
        metadata = {}

        for _ in range(n_kv):
            key = gguf_string(f)
            typ = u32(f)
            if key in ("general.alignment", "general.architecture", "split.no", "split.count"):
                metadata[key] = read_metadata_value(f, typ)
                if key == "general.alignment" and isinstance(metadata[key], int):
                    alignment = metadata[key]
            else:
                skip_scalar(f, typ)

        tensors = []
        for _ in range(n_tensors):
            name = gguf_string(f)
            n_dims = u32(f)
            dims = [u64(f) for _ in range(n_dims)]
            ggml_type = u32(f)
            offset = u64(f)
            tensors.append({
                "name": name,
                "dims": dims,
                "type": ggml_type,
                "offset": offset,
            })

        data_start = align_up(f.tell(), alignment)
        file_size = path.stat().st_size

    # Tensor offsets are relative to data_start.
    ordered = sorted(tensors, key=lambda t: t["offset"])
    for i, t in enumerate(ordered):
        start = data_start + t["offset"]
        if i + 1 < len(ordered):
            end = data_start + ordered[i + 1]["offset"]
        else:
            end = file_size
        t["disk_span_bytes"] = max(0, end - start)
        t["file"] = str(path)
        t["data_start"] = data_start

    return {
        "path": str(path),
        "version": version,
        "alignment": alignment,
        "metadata": metadata,
        "tensors": ordered,
    }

def resolve_inputs(items):
    found = []
    for raw in items:
        p = Path(raw)
        if p.is_dir():
            found.extend(sorted(p.glob("*.gguf")))
            continue
        matches = [Path(x) for x in glob.glob(raw)]
        if matches:
            found.extend(matches)
        elif p.is_file():
            found.append(p)
    # stable de-dupe
    uniq = []
    seen = set()
    for p in found:
        rp = str(p.resolve())
        if rp not in seen:
            seen.add(rp)
            uniq.append(Path(rp))
    return uniq

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gguf", nargs="+", help="GGUF file(s), directory, or glob(s)")
    ap.add_argument("--experts", type=int, default=128, help="experts per layer (default: 128)")
    ap.add_argument("--out", default="expert_size_report.json")
    args = ap.parse_args()

    files = resolve_inputs(args.gguf)
    if not files:
        raise SystemExit("No GGUF files found")

    all_tensors = []
    parsed = []
    for p in files:
        info = parse_gguf(p)
        parsed.append(info)
        all_tensors.extend(info["tensors"])
        print(f"[GGUF] {p.name}: v{info['version']} tensors={len(info['tensors'])} alignment={info['alignment']}")

    rx = re.compile(r"^blk\.(\d+)\.ffn_(gate|up|down)_exps\.weight$")
    layers = {}

    for t in all_tensors:
        m = rx.match(t["name"])
        if not m:
            continue
        layer = int(m.group(1))
        part = m.group(2)
        layers.setdefault(layer, {})[part] = t

    if not layers:
        print("\nNo blk.N.ffn_{gate,up,down}_exps.weight tensors found.")
        print("Candidate tensors containing '_exps':")
        for t in all_tensors:
            if "_exps" in t["name"]:
                print(" ", t["name"], t["dims"], t["disk_span_bytes"])
        raise SystemExit(2)

    report_layers = {}
    print("\n=== MoE expert bundle sizes ===")
    print("layer  gate MiB   up MiB   down MiB   bundle/expert MiB   parts")

    for layer in sorted(layers):
        parts = layers[layer]
        spans = {k: int(v["disk_span_bytes"]) for k, v in parts.items()}
        total_tensor_bytes = sum(spans.values())
        bundle = total_tensor_bytes / args.experts
        report_layers[str(layer)] = {
            "experts": args.experts,
            "gate_tensor_bytes": spans.get("gate", 0),
            "up_tensor_bytes": spans.get("up", 0),
            "down_tensor_bytes": spans.get("down", 0),
            "all_expert_tensors_bytes": total_tensor_bytes,
            "expert_bundle_bytes": bundle,
            "parts_present": sorted(parts.keys()),
            "tensor_names": {k: v["name"] for k, v in parts.items()},
            "files": {k: v["file"] for k, v in parts.items()},
        }
        mib = 1024**2
        print(f"{layer:5d}  "
              f"{spans.get('gate',0)/mib:8.3f} "
              f"{spans.get('up',0)/mib:8.3f} "
              f"{spans.get('down',0)/mib:9.3f} "
              f"{bundle/mib:18.3f}   "
              f"{','.join(sorted(parts))}")

    bundles = [v["expert_bundle_bytes"] for v in report_layers.values()]
    avg = sum(bundles) / len(bundles)
    total_expert_tensor_bytes = sum(v["all_expert_tensors_bytes"] for v in report_layers.values())

    summary = {
        "gguf_files": [str(p) for p in files],
        "n_layers_found": len(report_layers),
        "experts_per_layer": args.experts,
        "avg_expert_bundle_bytes": avg,
        "min_expert_bundle_bytes": min(bundles),
        "max_expert_bundle_bytes": max(bundles),
        "total_expert_tensor_bytes": total_expert_tensor_bytes,
        "layers": report_layers,
        "note": "Sizes use on-disk tensor spans and can include tiny GGUF alignment padding.",
    }

    out = Path(args.out)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    gib = 1024**3
    mib = 1024**2
    print("\n=== Summary ===")
    print(f"layers found             : {len(report_layers)}")
    print(f"experts/layer            : {args.experts}")
    print(f"avg expert bundle        : {avg/mib:.3f} MiB")
    print(f"min/max bundle           : {min(bundles)/mib:.3f} / {max(bundles)/mib:.3f} MiB")
    print(f"all expert tensors       : {total_expert_tensor_bytes/gib:.3f} GiB")
    print(f"report                    : {out.resolve()}")

if __name__ == "__main__":
    main()
