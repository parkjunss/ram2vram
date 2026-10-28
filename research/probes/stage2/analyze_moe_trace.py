#!/usr/bin/env python3
import csv
import re
import sys
from collections import defaultdict, OrderedDict

if len(sys.argv) < 2:
    raise SystemExit("usage: python analyze_moe_trace.py moe_expert_trace.csv")

path = sys.argv[1]

rows = []
with open(path, "r", encoding="utf-8-sig", newline="") as f:
    for r in csv.DictReader(f):
        r["call"] = int(r["call"])
        r["expert_id"] = int(r["expert_id"])
        r["n_experts_total"] = int(r["n_experts_total"])
        r["n_expert_used"] = int(r["n_expert_used"])
        r["n_tokens"] = int(r["n_tokens"])
        rows.append(r)

if not rows:
    raise SystemExit("trace is empty")

# Group rows by MMID call.
calls = defaultdict(list)
meta = {}
for r in rows:
    calls[r["call"]].append(r["expert_id"])
    meta[r["call"]] = r

# Extract a layer key from tensor name when possible.
def layer_key(name):
    m = re.search(r"blk\.(\d+)\.", name)
    if m:
        return f"blk.{int(m.group(1))}"
    return name

# Multiple expert matmuls in one layer/token can reuse the same routing IDs.
# Collapse consecutive calls with the same layer + same expert tuple.
events = []
prev = None
for c in sorted(calls):
    r = meta[c]
    key = layer_key(r["tensor"])
    ids = tuple(calls[c])
    sig = (key, ids)
    if sig == prev:
        continue
    events.append((c, key, r["tensor"], ids, r["n_experts_total"]))
    prev = sig

print("=== Trace summary ===")
print(f"raw MMID calls       : {len(calls)}")
print(f"collapsed route events: {len(events)}")
print(f"layers seen          : {len(set(e[1] for e in events))}")
print(f"expert IDs/event     : {len(events[0][3]) if events else 0}")
print()

# Frequency.
freq = defaultdict(int)
for _, layer, _, ids, _ in events:
    for eid in ids:
        freq[(layer, eid)] += 1

# Per-layer LRU simulation: cache size = number of expert bundles resident per layer.
capacities = [2, 4, 8, 16, 32, 64]
hits = {c: 0 for c in capacities}
miss = {c: 0 for c in capacities}
caches = {c: defaultdict(OrderedDict) for c in capacities}

for _, layer, _, ids, _ in events:
    for eid in ids:
        for cap in capacities:
            cache = caches[cap][layer]
            if eid in cache:
                hits[cap] += 1
                cache.move_to_end(eid)
            else:
                miss[cap] += 1
                cache[eid] = None
                if len(cache) > cap:
                    cache.popitem(last=False)

print("=== Per-layer LRU expert-cache simulation ===")
for cap in capacities:
    total = hits[cap] + miss[cap]
    rate = 100.0 * hits[cap] / total if total else 0.0
    print(f"cache {cap:2d}/layer : hit {rate:6.2f}%  "
          f"({hits[cap]}/{total})")
print()

# Unique experts touched per layer.
per_layer = defaultdict(set)
for _, layer, _, ids, _ in events:
    per_layer[layer].update(ids)

counts = [len(v) for v in per_layer.values()]
print("=== Unique experts touched ===")
if counts:
    print(f"min/layer : {min(counts)}")
    print(f"avg/layer : {sum(counts)/len(counts):.2f}")
    print(f"max/layer : {max(counts)}")
print()

print("=== First 30 collapsed routing events ===")
for c, layer, tensor, ids, total in events[:30]:
    print(f"call={c:5d} {layer:8s} ids={list(ids)} tensor={tensor}")
