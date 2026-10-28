# Research artifacts

This directory contains the analysis code, instrumentation, traces, and compact benchmark results behind the RAM2VRAM report.

## What is final and reusable

- `global-cache/`: inspects GGUF expert tensors and simulates a byte-budgeted global LRU cache.
- `optimizer/`: compares global LRU with static layer residency under a fixed VRAM budget.
- `data/traces/`: raw routing traces for independent reanalysis.
- `data/gpt_oss_expert_sizes.json`: sanitized per-layer expert sizes. Local model paths were removed.
- `results/benchmark-summary.csv`: one row per measured configuration. Raw logs remain local because they contain machine paths.

## Instrumentation

- `probes/stage1/`: locates the llama.cpp MoE execution path.
- `probes/stage2/`: injects a CUDA routing probe and analyzes the resulting trace.
- `probes/cpu/`: instruments the CPU-MoE path.

The probe scripts modify a separate llama.cpp checkout. Use them only on a clean, disposable checkout and pass its path explicitly. Restore scripts reverse only the corresponding probe changes.

## Failed or superseded approaches

The persistent slot-remap cache is retained as a negative result in the report: the cache-off baseline was about 8.2 tok/s, while 8–16 slots achieved only 3.1–3.3 tok/s. The implementation is not presented as the recommended path.

The hybrid cache is the successful runtime direction. Its llama.cpp implementation is fetched at a pinned commit by `scripts/windows/setup_hybrid_moe_cache.bat`; the third-party checkout is intentionally not vendored here.

## Reproduce the analysis

```bat
python research\probes\stage2\analyze_moe_trace.py research\data\traces\moe_expert_trace_all.csv
python research\global-cache\simulate_global_expert_cache.py research\data\traces\moe_expert_trace_all.csv research\data\gpt_oss_expert_sizes.json
python research\optimizer\optimize_vram_allocation.py research\data\traces\moe_expert_trace_all.csv research\data\gpt_oss_expert_sizes.json --budgets-gib 4,8,12
```

The full trace contains 55 inferred decode steps across all 36 MoE layers. The longer partial trace contains 127 steps across layers 7–35. Keep those scopes separate when comparing hit rates.
