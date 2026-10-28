#pragma once

// gpt-oss MoE expert-ID probe for current monolithic ggml-cuda.cu.
// Probe only: intentionally synchronizes the CUDA stream for D2H ID logging.
// Do NOT benchmark performance with RAM2VRAM_MOE_PROBE=1.

#include <cuda_runtime.h>

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>

struct ram2vram_moe_probe_state {
    uint64_t call_index = 0;
};

static inline ram2vram_moe_probe_state & ram2vram_moe_probe_get_state() {
    static ram2vram_moe_probe_state s;
    return s;
}

static inline bool ram2vram_moe_probe_enabled() {
    const char * v = std::getenv("RAM2VRAM_MOE_PROBE");
    return v != nullptr && std::strcmp(v, "0") != 0;
}

static inline int ram2vram_moe_probe_limit() {
    const char * v = std::getenv("RAM2VRAM_MOE_PROBE_LIMIT");
    if (!v || !*v) {
        return 2000;
    }
    const int n = std::atoi(v);
    return n > 0 ? n : 2000;
}

static inline FILE * ram2vram_moe_probe_file() {
    static FILE * fp = nullptr;
    static std::once_flag once;

    std::call_once(once, []() {
        const char * path = std::getenv("RAM2VRAM_MOE_PROBE_OUT");
        if (!path || !*path) {
            path = "moe_expert_trace.csv";
        }

#ifdef _WIN32
        fopen_s(&fp, path, "wb");
#else
        fp = std::fopen(path, "wb");
#endif
        if (fp) {
            std::fprintf(fp,
                "call,tensor,n_experts_total,n_expert_used,n_tokens,expert_slot,expert_id\n");
            std::fflush(fp);
        } else {
            std::fprintf(stderr,
                "[RAM2VRAM-MOE] failed to open trace output\n");
        }
    });

    return fp;
}

static inline void ram2vram_probe_moe_ids(
    ggml_backend_cuda_context & ctx,
    const ggml_tensor * src0,
    const ggml_tensor * src1,
    const ggml_tensor * ids,
    const ggml_tensor * dst) {

    if (!ram2vram_moe_probe_enabled()) {
        return;
    }
    if (!src0 || !src1 || !ids || !dst) {
        return;
    }

    // For MUL_MAT_ID in current llama.cpp:
    // ids->ne[0] = experts selected per token.
    // src1->ne[2] is the token dimension used by the CUDA MMID path.
    const int64_t n_expert_used = ids->ne[0];
    const int64_t n_tokens      = src1->ne[2];
    const int64_t n_experts     = src0->ne[2];

    // We care about autoregressive decode locality first.
    if (n_tokens != 1) {
        return;
    }

    if (ids->type != GGML_TYPE_I32) {
        static bool warned = false;
        if (!warned) {
            warned = true;
            std::fprintf(stderr,
                "[RAM2VRAM-MOE] unexpected ids type=%d; expected GGML_TYPE_I32\n",
                (int) ids->type);
        }
        return;
    }

    if (n_expert_used <= 0 || n_expert_used > 256) {
        return;
    }

    auto & st = ram2vram_moe_probe_get_state();
    if ((int) st.call_index >= ram2vram_moe_probe_limit()) {
        return;
    }

    std::vector<int32_t> host_ids((size_t) n_expert_used);

    cudaStream_t stream = ctx.stream();

    cudaError_t err = cudaMemcpyAsync(
        host_ids.data(),
        ids->data,
        (size_t) n_expert_used * sizeof(int32_t),
        cudaMemcpyDeviceToHost,
        stream);

    if (err != cudaSuccess) {
        std::fprintf(stderr,
            "[RAM2VRAM-MOE] cudaMemcpyAsync(ids) failed: %s\n",
            cudaGetErrorString(err));
        return;
    }

    // Probe mode intentionally synchronizes so the CSV contains exact IDs.
    err = cudaStreamSynchronize(stream);
    if (err != cudaSuccess) {
        std::fprintf(stderr,
            "[RAM2VRAM-MOE] cudaStreamSynchronize failed: %s\n",
            cudaGetErrorString(err));
        return;
    }

    FILE * fp = ram2vram_moe_probe_file();
    const uint64_t call = st.call_index++;

    if (call < 32) {
        std::fprintf(stderr,
            "[RAM2VRAM-MOE] call=%llu tensor=%s experts=",
            (unsigned long long) call,
            src0->name);

        for (int64_t i = 0; i < n_expert_used; ++i) {
            std::fprintf(stderr, "%s%d", i ? "," : "", host_ids[(size_t) i]);
        }
        std::fprintf(stderr,
            " total=%lld used=%lld\n",
            (long long) n_experts,
            (long long) n_expert_used);
        std::fflush(stderr);
    }

    if (fp) {
        for (int64_t i = 0; i < n_expert_used; ++i) {
            std::fprintf(fp,
                "%llu,\"%s\",%lld,%lld,%lld,%lld,%d\n",
                (unsigned long long) call,
                src0->name,
                (long long) n_experts,
                (long long) n_expert_used,
                (long long) n_tokens,
                (long long) i,
                host_ids[(size_t) i]);
        }
        std::fflush(fp);
    }
}
