#!/usr/bin/env python3
import csv, re, sys
from collections import defaultdict, OrderedDict
if len(sys.argv) < 2:
    raise SystemExit("usage: python analyze_moe_trace.py moe_expert_trace.csv")
rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8-sig", newline="")))
if not rows:
    raise SystemExit("trace is empty")
calls = defaultdict(list); meta = {}
for r in rows:
    c = int(r["call"]); calls[c].append(int(r["expert_id"])); meta[c] = r

def layer_key(name):
    m = re.search(r"blk\.(\d+)\.", name)
    return f"blk.{m.group(1)}" if m else name

events=[]; prev=None
for c in sorted(calls):
    r=meta[c]; key=layer_key(r["tensor"]); ids=tuple(calls[c]); sig=(key,ids)
    if sig == prev: continue
    events.append((c,key,r["tensor"],ids)); prev=sig

print("=== Trace summary ===")
print("raw MMID calls        :", len(calls))
print("collapsed route events:", len(events))
print("layers seen           :", len(set(e[1] for e in events)))
print("expert IDs/event      :", len(events[0][3]) if events else 0)
print()
for cap in [2,4,8,16,32,64]:
    hits=miss=0; caches=defaultdict(OrderedDict)
    for _,layer,_,ids in events:
        for eid in ids:
            cache=caches[layer]
            if eid in cache:
                hits += 1; cache.move_to_end(eid)
            else:
                miss += 1; cache[eid]=None
                if len(cache) > cap: cache.popitem(last=False)
    total=hits+miss
    print(f"cache {cap:2d}/layer : hit {(100*hits/total if total else 0):6.2f}% ({hits}/{total})")
print()
per_layer=defaultdict(set)
for _,layer,_,ids in events: per_layer[layer].update(ids)
counts=[len(v) for v in per_layer.values()]
print("=== Unique experts touched ===")
if counts:
    print("min/layer :", min(counts)); print("avg/layer :", round(sum(counts)/len(counts),2)); print("max/layer :", max(counts))
print()
print("=== First 30 events ===")
for c,layer,tensor,ids in events[:30]:
    print(f"call={c:5d} {layer:8s} ids={list(ids)} tensor={tensor}")
