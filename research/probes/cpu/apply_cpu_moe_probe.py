#!/usr/bin/env python3
from pathlib import Path
import shutil, sys

if len(sys.argv) != 2:
    raise SystemExit(r"usage: python apply_cpu_moe_probe.py C:\path\to\llama.cpp")

root = Path(sys.argv[1]).resolve()
target = root / "ggml" / "src" / "ggml-cpu" / "ggml-cpu.c"
if not target.exists():
    raise SystemExit("ERROR: ggml-cpu.c not found")

text = target.read_text(encoding="utf-8", errors="replace")
backup = target.with_suffix(target.suffix + ".moe-probe.bak")
if not backup.exists():
    shutil.copy2(target, backup)

helper = r'''
// ---- RAM2VRAM CPU MoE probe ------------------------------------------------
static int ram2vram_cpu_moe_probe_enabled(void) {
    const char * v = getenv("RAM2VRAM_MOE_PROBE");
    return v != NULL && strcmp(v, "0") != 0;
}

static int ram2vram_cpu_moe_probe_limit(void) {
    const char * v = getenv("RAM2VRAM_MOE_PROBE_LIMIT");
    if (v == NULL || *v == '\0') return 4000;
    const int n = atoi(v);
    return n > 0 ? n : 4000;
}

static FILE * ram2vram_cpu_moe_probe_file(void) {
    static FILE * fp = NULL;
    static int initialized = 0;
    if (!initialized) {
        initialized = 1;
        const char * path = getenv("RAM2VRAM_MOE_PROBE_OUT");
        if (path == NULL || *path == '\0') path = "moe_expert_trace.csv";
#ifdef _WIN32
        fopen_s(&fp, path, "wb");
#else
        fp = fopen(path, "wb");
#endif
        if (fp != NULL) {
            fprintf(fp, "call,tensor,n_experts_total,n_expert_used,n_tokens,expert_slot,expert_id\\n");
            fflush(fp);
        }
    }
    return fp;
}

static void ram2vram_cpu_probe_moe_ids(
        const struct ggml_tensor * src0,
        const struct ggml_tensor * src1,
        const struct ggml_tensor * ids,
        const struct ggml_tensor * dst) {
    GGML_UNUSED(dst);
    if (!ram2vram_cpu_moe_probe_enabled()) return;
    if (src0 == NULL || src1 == NULL || ids == NULL) return;

    const int64_t n_expert_used   = ids->ne[0];
    const int64_t n_tokens        = ids->ne[1];
    const int64_t n_experts_total = src0->ne[2];

    if (n_tokens != 1) return;
    if (ids->type != GGML_TYPE_I32) return;
    if (n_expert_used <= 0 || n_expert_used > 256) return;

    static uint64_t call_index = 0;
    if ((int) call_index >= ram2vram_cpu_moe_probe_limit()) return;

    const int32_t * idata = (const int32_t *) ids->data;
    const uint64_t call = call_index++;

    if (call < 64) {
        fprintf(stderr, "[RAM2VRAM-MOE-CPU] call=%llu tensor=%s experts=",
                (unsigned long long) call, src0->name);
        for (int64_t i = 0; i < n_expert_used; ++i) {
            fprintf(stderr, "%s%d", i ? "," : "", idata[i]);
        }
        fprintf(stderr, " total=%lld used=%lld\\n",
                (long long) n_experts_total, (long long) n_expert_used);
        fflush(stderr);
    }

    FILE * fp = ram2vram_cpu_moe_probe_file();
    if (fp != NULL) {
        for (int64_t i = 0; i < n_expert_used; ++i) {
            fprintf(fp, "%llu,\"%s\",%lld,%lld,%lld,%lld,%d\\n",
                    (unsigned long long) call, src0->name,
                    (long long) n_experts_total,
                    (long long) n_expert_used,
                    (long long) n_tokens,
                    (long long) i,
                    idata[i]);
        }
        fflush(fp);
    }
}
// -----------------------------------------------------------------------------
'''

if "ram2vram_cpu_probe_moe_ids" not in text:
    marker = "// ggml_compute_forward_mul_mat_id"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("ERROR: MUL_MAT_ID section marker not found")
    text = text[:pos] + helper + "\n" + text[pos:]

sig = "static void ggml_compute_forward_mul_mat_id("
pos = text.find(sig)
if pos < 0:
    raise SystemExit("ERROR: ggml_compute_forward_mul_mat_id not found")

brace = text.find("{", pos)
search_end = min(len(text), brace + 10000)
ids_pos = -1
for needle in ("const struct ggml_tensor * ids", "const ggml_tensor * ids"):
    ids_pos = text.find(needle, brace, search_end)
    if ids_pos >= 0:
        break
if ids_pos < 0:
    raise SystemExit("ERROR: ids declaration not found inside MUL_MAT_ID")

line_end = text.find("\n", ids_pos)
call = "\n    ram2vram_cpu_probe_moe_ids(src0, src1, ids, dst);\n"
if "ram2vram_cpu_probe_moe_ids(src0, src1, ids, dst);" not in text:
    text = text[:line_end+1] + call + text[line_end+1:]

target.write_text(text, encoding="utf-8")
print("PATCHED:", target)
print("BACKUP :", backup)
