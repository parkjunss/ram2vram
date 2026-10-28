#!/usr/bin/env python3
"""
Simulate a global VRAM expert cache using real (layer, expert) routing trace
and per-layer expert bundle sizes from inspect_gpt_oss_expert_sizes.py.

Cache key: (layer, expert_id)
Policy: true byte-budget LRU
Miss cost: transfer one gate+up+down expert bundle for that layer
"""

from __future__ import annotations
import argparse
import csv
import json
import re
from collections import OrderedDict, defaultdict

def load_events(csv_path):
    calls = defaultdict(list)
    meta = {}
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            c = int(r["call"])
            calls[c].append(int(r["expert_id"]))
            meta[c] = r

    if not calls:
        raise SystemExit("Trace is empty")

    def layer_from_name(name):
        m = re.search(r"blk\.(\d+)\.", name)
        return int(m.group(1)) if m else None

    # Collapse gate/up/down calls sharing the same routing decision.
    events = []
    prev = None
    for c in sorted(calls):
        name = meta[c]["tensor"]
        layer = layer_from_name(name)
        ids = tuple(calls[c])
        sig = (layer, ids)
        if sig == prev:
            continue
        events.append((c, layer, ids, name))
        prev = sig
    return events

def simulate(events, layer_sizes, budget_bytes):
    cache = OrderedDict()   # (layer,eid) -> bytes
    used = 0
    hits = misses = 0
    bytes_xfer = 0
    compulsory = set()
    evictions = 0

    for _, layer, ids, _ in events:
        key_layer = str(layer)
        if key_layer not in layer_sizes:
            continue
        bundle = int(round(layer_sizes[key_layer]["expert_bundle_bytes"]))

        for eid in ids:
            key = (layer, eid)
            if key in cache:
                hits += 1
                cache.move_to_end(key)
                continue

            misses += 1
            bytes_xfer += bundle
            compulsory.add(key)

            # If a single expert bundle exceeds budget, it can never reside.
            if bundle > budget_bytes:
                continue

            while cache and used + bundle > budget_bytes:
                _, old_bytes = cache.popitem(last=False)
                used -= old_bytes
                evictions += 1

            cache[key] = bundle
            used += bundle

    total = hits + misses
    return {
        "hits": hits,
        "misses": misses,
        "accesses": total,
        "hit_rate": hits / total if total else 0.0,
        "bytes_xfer": bytes_xfer,
        "unique_pairs": len(compulsory),
        "evictions": evictions,
        "final_cache_entries": len(cache),
        "final_cache_bytes": used,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("trace_csv")
    ap.add_argument("size_report_json")
    ap.add_argument("--budgets-gib", default="0.5,1,2,3,4,6,8,10,12")
    ap.add_argument("--pcie-gbps", type=float, default=14.2,
                    help="Measured H2D GB/s, decimal GB/s (default 14.2)")
    args = ap.parse_args()

    events = load_events(args.trace_csv)
    report = json.load(open(args.size_report_json, "r", encoding="utf-8"))
    layer_sizes = report["layers"]

    layers = sorted({layer for _, layer, _, _ in events if str(layer) in layer_sizes})
    if not layers:
        raise SystemExit("No trace layers matched size report")

    # Infer token steps from routing events / participating layers.
    # The trace is layer-major and should contain one routing event per MoE layer per decode token.
    token_steps = len([e for e in events if e[1] in layers]) / len(layers)

    budgets = [float(x.strip()) for x in args.budgets_gib.split(",") if x.strip()]
    GiB = 1024**3
    MiB = 1024**2

    print("=== Global expert-cache simulation ===")
    print(f"routing events      : {len(events)}")
    print(f"matched layers      : {len(layers)} ({layers[0]}..{layers[-1]})")
    print(f"estimated tokens    : {token_steps:.2f}")
    print(f"PCIe H2D assumption : {args.pcie_gbps:.2f} GB/s")
    print()
    print("budget  hit-rate   misses/tok   xfer MiB/tok   PCIe ms/tok   PCIe-only max tok/s   entries(end)")

    for gib in budgets:
        r = simulate(events, layer_sizes, int(gib * GiB))
        misses_per_tok = r["misses"] / token_steps
        mib_per_tok = (r["bytes_xfer"] / MiB) / token_steps
        # decimal GB/s as measured convention
        pcie_ms = (r["bytes_xfer"] / token_steps) / (args.pcie_gbps * 1e9) * 1000.0
        max_tps = 1000.0 / pcie_ms if pcie_ms > 0 else float("inf")

        print(f"{gib:5.1f}G  "
              f"{r['hit_rate']*100:7.2f}%   "
              f"{misses_per_tok:10.2f}   "
              f"{mib_per_tok:12.2f}   "
              f"{pcie_ms:11.3f}   "
              f"{max_tps:18.2f}   "
              f"{r['final_cache_entries']:11d}")

    # Infinite-cache lower bound: compulsory misses only.
    # Make budget huge enough to retain every observed pair.
    huge = 1 << 60
    inf = simulate(events, layer_sizes, huge)
    pcie_ms = (inf["bytes_xfer"] / token_steps) / (args.pcie_gbps * 1e9) * 1000.0
    print()
    print("=== Observed-trace compulsory-miss lower bound ===")
    print(f"unique (layer,expert) pairs : {inf['unique_pairs']}")
    print(f"hit rate                   : {inf['hit_rate']*100:.2f}%")
    print(f"misses/token               : {inf['misses']/token_steps:.2f}")
    print(f"transfer/token             : {(inf['bytes_xfer']/MiB)/token_steps:.2f} MiB")
    print(f"PCIe lower bound           : {pcie_ms:.3f} ms/token")
    if pcie_ms > 0:
        print(f"PCIe-only upper bound      : {1000/pcie_ms:.2f} tok/s")
    print()
    print("NOTE: This is a transfer-only bound. Real runtime also includes routing,")
    print("GPU expert compute, attention, synchronization, cache metadata, and overlap.")

if __name__ == "__main__":
    main()
