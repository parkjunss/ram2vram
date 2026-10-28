#!/usr/bin/env python3
import argparse,csv,json,re
from collections import OrderedDict,defaultdict
GiB=1024**3; MiB=1024**2

def load_events(path):
    calls=defaultdict(list); meta={}
    with open(path,encoding="utf-8-sig",newline="") as f:
        for r in csv.DictReader(f):
            c=int(r["call"]); calls[c].append(int(r["expert_id"])); meta[c]=r
    events=[]; prev=None
    for c in sorted(calls):
        m=re.search(r"blk\.(\d+)\.",meta[c]["tensor"])
        if not m: continue
        layer=int(m.group(1)); ids=tuple(calls[c]); sig=(layer,ids)
        if sig==prev: continue
        events.append((layer,ids)); prev=sig
    return events

def simulate(events,sizes,budget,static_layers=frozenset()):
    static_bytes=sum(int(round(sizes[str(l)]["expert_bundle_bytes"]*sizes[str(l)]["experts"])) for l in static_layers)
    dyn=max(0,budget-static_bytes); cache=OrderedDict(); used=hits=misses=xfer=0
    for layer,ids in events:
        b=int(round(sizes[str(layer)]["expert_bundle_bytes"]))
        for eid in ids:
            if layer in static_layers:
                hits+=1; continue
            key=(layer,eid)
            if key in cache:
                hits+=1; cache.move_to_end(key)
            else:
                misses+=1; xfer+=b
                if b<=dyn:
                    while cache and used+b>dyn:
                        _,old=cache.popitem(last=False); used-=old
                    cache[key]=b; used+=b
    return static_bytes,dyn,hits,misses,xfer,len(cache)

def metrics(r,tokens,gbps):
    _,_,h,m,x,_=r; total=h+m
    hit=h/total if total else 0
    mib=(x/MiB)/tokens
    ms=(x/tokens)/(gbps*1e9)*1000
    return hit,mib,ms

def greedy(events,sizes,layers,budget):
    chosen=set(); cur=simulate(events,sizes,budget,chosen)
    while True:
        best_layer=None; best=cur
        for l in layers:
            if l in chosen: continue
            tr=simulate(events,sizes,budget,chosen|{l})
            if tr[0]<=budget and tr[4]<best[4]:
                best_layer=l; best=tr
        if best_layer is None: return chosen,cur
        chosen.add(best_layer); cur=best

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("trace_csv"); ap.add_argument("size_json")
    ap.add_argument("--budgets-gib",default="4,6,8,10,12")
    ap.add_argument("--pcie-gbps",type=float,default=14.2)
    a=ap.parse_args()
    events=load_events(a.trace_csv)
    rep=json.load(open(a.size_json,encoding="utf-8")); sizes=rep["layers"]
    layers=sorted({l for l,_ in events if str(l) in sizes})
    counts=defaultdict(int)
    for l,_ in events: counts[l]+=1
    tokens=min(counts[l] for l in layers)
    avg=sum(float(sizes[str(l)]["expert_bundle_bytes"]) for l in layers)/len(layers)
    full=avg*rep["experts_per_layer"]
    print("=== Trace / model ===")
    print(f"layers in trace       : {len(layers)} ({layers[0]}..{layers[-1]})")
    print(f"decode steps inferred : {tokens}")
    print(f"expert bundle avg     : {avg/MiB:.3f} MiB")
    print(f"full expert layer     : {full/GiB:.3f} GiB\n")
    for bg in map(float,a.budgets_gib.split(",")):
        budget=int(bg*GiB)
        base=simulate(events,sizes,budget); h,mib,ms=metrics(base,tokens,a.pcie_gbps)
        print(f"=== {bg:.1f} GiB expert budget ===")
        print(f"GLOBAL-LRU : hit={h*100:6.2f}% xfer={mib:8.2f} MiB/tok PCIe={ms:7.3f} ms/tok")
        best=None
        for n in range(1,len(layers)+1):
            st=set(layers[:n]); r=simulate(events,sizes,budget,st)
            if r[0]>budget: break
            mm=metrics(r,tokens,a.pcie_gbps)
            if best is None or r[4]<best[2][4]: best=(n,mm,r)
        if best:
            n,(h,mib,ms),r=best
            print(f"BEST PREFIX: pin={n:2d} static={r[0]/GiB:5.2f}G dyn={r[1]/GiB:5.2f}G hit={h*100:6.2f}% xfer={mib:8.2f} MiB/tok PCIe={ms:7.3f} ms/tok")
        ch,r=greedy(events,sizes,layers,budget); h,mib,ms=metrics(r,tokens,a.pcie_gbps)
        print(f"GREEDY PIN : pin={len(ch):2d} {sorted(ch)} static={r[0]/GiB:5.2f}G dyn={r[1]/GiB:5.2f}G hit={h*100:6.2f}% xfer={mib:8.2f} MiB/tok PCIe={ms:7.3f} ms/tok\n")
if __name__=="__main__": main()
