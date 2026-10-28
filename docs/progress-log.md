# RAM → VRAM LLM Streaming 실험 정리

작성일: 2026-09-16

## 1. 프로젝트 목표

이 프로젝트의 목표는 **대형 LLM의 전체 weight를 VRAM에 상주시킬 수 없는 환경에서, system RAM을 주 저장소로 사용하고 필요한 weight만 GPU로 빠르게 전송하여 실행하는 구조**를 검증하는 것이다.

핵심 아이디어는 다음과 같다.

- System RAM에 전체 또는 대부분의 LLM weight 저장
- VRAM에는 작은 hot cache / ring buffer / A-B buffer만 유지
- 필요 weight를 CUDA async H2D로 전송
- 전송과 GPU compute를 overlap
- quantized weight를 RAM에서 그대로 전송하고 GPU에서 dequant / compute
- 최종적으로 llama.cpp / GGUF 기반 실제 LLM inference에 통합
- Dense model보다 MoE model에서 **router-selected expert streaming/cache**를 활용

핵심 KPI는 단순 PCIe 대역폭이 아니라 다음이다.

- bytes transferred / token
- exposed PCIe stall / token
- cache hit rate
- effective tok/s
- RAM → VRAM streaming으로 인한 추가 latency

---

# 2. 테스트 환경

## Hardware

- CPU: AMD Ryzen 7 7800X3D
- GPU: NVIDIA GeForce RTX 5060 Ti
- VRAM: 16 GB
- System RAM: 64 GB
- GPU Compute Capability: 12.0
- SM: 36
- asyncEngineCount: 1
- concurrent kernels: supported

## PCIe

- GPU capability: PCIe Gen5
- Host maximum: PCIe Gen4
- Link width: x8
- Idle 시 Gen2로 낮아지는 power saving 동작 확인
- 실제 active link 성능은 사실상 PCIe 4.0 x8

## Software

- Windows
- CUDA Toolkit 12.8
- nvcc 12.8.61
- Visual Studio 2022 Community
- MSVC 19.43 / 14.43 toolset
- llama.cpp stock build: b10986-6011c34ce
- llama.cpp configure 당시 버전: 0.4.1-dev 계열

---

# 3. CUDA 기본 H2D 대역폭 측정

Pinned host memory 기반 H2D 전송 테스트 결과:

- 1024 MiB × 20: 약 14.28 GB/s
- 2048 MiB × 30: 약 14.27 GB/s
- Write-combined pinned memory: 약 14.25 GB/s
- 복수 H2D stream: 유의미한 개선 없음

## 결론

현재 시스템에서 실사용 가능한 H2D throughput은 약:

```text
14.1 ~ 14.3 GB/s
```

정도이며 PCIe 4.0 x8의 practical limit에 거의 도달한다.

즉 이후 최적화는 PCIe peak bandwidth 자체보다:

```text
전송량 감소
+ compute overlap
+ cache hit
```

가 핵심이다.

---

# 4. Synthetic H2D + Compute overlap

파일:

```text
/mnt/data/compute_h2d_overlap/compute_h2d_overlap.cu
```

512 MiB 기준:

```text
copy       37.805 ms
compute    35.213 ms
sequential 72.842 ms
concurrent 38.820 ms
hidden     34.198 ms
overlap efficiency 97.118%
penalty    2.684%
speedup    1.876x
```

## 결론

CUDA compute와 H2D copy는 거의 완전히 overlap 가능하다.

즉 runtime 구조를 잘 만들면 H2D latency 대부분을 compute 뒤에 숨길 수 있다.

---

# 5. cuBLAS GEMM + H2D overlap

파일:

```text
/mnt/data/cublas_h2d_overlap/
```

### repeats = 16

```text
copy       37.896 ms
GEMM       24.875 ms
concurrent 37.836 ms
overlap    ~100%
```

### repeats = 32

```text
copy       37.831 ms
GEMM       49.943 ms
concurrent 52.810 ms
overlap    92.422%
```

## 결론

실제 GEMM과 PCIe copy도 높은 수준으로 겹칠 수 있다.

---

# 6. FP16 A/B Double Buffer Streaming

파일:

```text
/mnt/data/double_buffer_streaming/
```

Matrix:

```text
4096 × 4096 FP16
= 32 MiB/layer
```

64 layer × 5 기준:

```text
sequential 4.057 ms/layer
streaming  2.397 ms/layer
417.1 layers/s
effective H2D 13.996 GB/s
speedup 1.692x
```

## 결론

FP16 전체 weight streaming에서는 정확히 PCIe bottleneck이 된다.

---

# 7. Q4 Transport + Dequant + cuBLAS

파일:

```text
/mnt/data/q4_double_buffer_streaming/
```

실험용 signed Q4:

```text
FP16 weight 32 MiB
Q4 weight    8 MiB
```

결과:

```text
Q4 H2D    0.598 ms
dequant   0.120 ms
GEMM      1.534 ms
compute   1.654 ms
stream    1.722 ms

FP16-equivalent bandwidth:
19.484 GB/s
```

## 결론

compression으로 PCIe 비용을 compute 뒤로 밀어낼 수 있었다.

---

# 8. Block Q4 + Fused WMMA

파일:

```text
/mnt/data/block_q4_fused_streaming/
```

Block 구조:

```cpp
Q4Block32 {
    __half scale;
    uint8_t qs[16];
}
```

실질 약 4.5 bit/weight.

Matrix:

```text
M=128
N=4096
K=4096
```

결과:

```text
weight     9 MiB
H2D        0.674 ms
fused      0.867 ms
sequential 1.641 ms
streaming  1.276 ms
FP16 eq    26.289 GB/s
```

---

# 9. 4-way Profiler

파일:

```text
/mnt/data/fused_q4_4way_profiler/
```

결과:

```text
H2D              0.668 ms
fused compute    0.907 ms
no-overlap       1.575 ms
ideal            0.907 ms
raw concurrent   0.955 ms
A/B pipeline     1.160 ms

raw overlap      92.896%
interference     5.226%
pipeline extra   0.206 ms
```

Sanity check:

```text
PASS
```

---

# 10. Grouped Double Buffer

파일:

```text
/mnt/data/grouped_double_buffer/
```

최적값:

```text
Group = 1
1.116 ms/layer
896.34 layers/s

Q4 bandwidth   8.459 GB/s
FP16 equivalent 30.076 GB/s
```

Group 2/4/8은 더 느렸다.

## 결론

현재 workload에서는 큰 group batching보다 layer 단위 streaming이 유리했다.

---

# 11. CUDA Graph vs Classic Event Pipeline

파일:

```text
/mnt/data/cuda_graph_ab_benchmark/
```

결과:

```text
classic       1.161 ms
graph sync    1.183 ms
graph batched 1.173 ms
```

## 결론

host orchestration overhead는 병목이 아니었다.

Kernel 자체와 memory traffic 최적화가 더 중요하다.

---

# 12. Multi-warp Q4 Kernel

파일:

```text
/mnt/data/multiwarp_q4_benchmark/
```

### baseline single warp

```text
fused  0.913 ms
stream 1.159 ms
862 layers/s
```

### 4-warp / 128-thread version

```text
fused  0.447 ms
stream 0.710 ms
1409 layers/s

Q4 bandwidth   13.299 GB/s
FP16 equivalent 47.284 GB/s

fused speedup     2.045x
streaming speedup 1.634x
```

## 결론

compute가 크게 빨라지면서 다시 PCIe가 bottleneck이 됐다.

---

# 13. Q4 / Q3 / Q2 비교

파일:

```text
/mnt/data/q234_multiwarp_streaming/
```

결과:

```text
Q4:
weight 9 MiB
H2D    0.670 ms
fused  0.455 ms
stream 0.718 ms
H2D/compute = 1.471
=> PCIe bottleneck

Q3:
weight 7 MiB
H2D    0.521 ms
fused  0.478 ms
stream 0.611 ms
H2D/compute = 1.09
=> 거의 balanced

Q2:
weight 5 MiB
H2D    0.373 ms
fused  0.443 ms
stream 0.508 ms
H2D/compute = 0.842
=> compute bottleneck
```

## 결론

synthetic prefill-style workload에서는 Q2가 가장 유리했다.

---

# 14. Decode GEMV Q4/Q3/Q2

파일:

```text
/mnt/data/decode_q234_gemv/
```

Batch 1:

```text
Q4:
H2D   0.671 ms
GEMV  0.039 ms
stream 0.672 ms
1487 layer/s
H2D/GEMV = 17.18

Q3:
H2D   0.523 ms
GEMV  0.066 ms
stream 0.528 ms
1893 layer/s
H2D/GEMV = 7.97

Q2:
H2D   0.375 ms
GEMV  0.040 ms
stream 0.389 ms
2573 layer/s
H2D/GEMV = 9.45
```

Q2 batch:

```text
batch2 0.380 ms
batch4 0.381 ms
batch8 0.386 ms
```

## 결론

Decode에서는 weight streaming 비용이 compute보다 압도적으로 크다.

Dense model의 전체-weight RAM → VRAM decode streaming은 구조적으로 불리하다.

---

# 15. Granite 4.1 8B 실제 GGUF 조사

Ollama blob:

```text
<local-model-cache>/sha256-ed902ac9eb6adce5a90c6a08c8ea201b50e23fdc5976d1cd0362006afac5309e
```

GGUF inspector:

```text
/mnt/data/gguf_inspector/
```

모델 정보:

```text
GGUF v3
363 tensors
40 blocks
embedding = 4096
FFN = 12800
```

Tensor type 규모:

```text
F32   : 81 tensors, ~1.27 MiB
Q4_K  : 241 tensors, ~3888 MiB
Q6_K  : 41 tensors, ~1207.5 MiB
```

Block 0 주요 tensor:

```text
attn_k      Q4_K  [4096 x 1024]   2.25 MiB
attn_output Q4_K  [4096 x 4096]   9 MiB
attn_q      Q4_K  [4096 x 4096]   9 MiB
attn_v      Q6_K  [4096 x 1024]   3.28 MiB
ffn_down    Q6_K  [12800 x 4096] 41.016 MiB
ffn_gate    Q4_K  [4096 x 12800] 28.125 MiB
ffn_up      Q4_K  [4096 x 12800] 28.125 MiB
```

---

# 16. 실제 Granite Q4_K GEMV

파일:

```text
/mnt/data/real_q4k_gemv/
```

실제:

```text
blk.0.attn_q.weight
size = 9 MiB
Q4_K = 144 bytes / 256 weights
```

Correctness:

```text
max abs error = 7e-8
relative      = 8.9e-7
PASS
```

성능:

```text
H2D       0.670 ms
GEMV      0.042 ms
A/B stream 0.674 ms

payload bandwidth = 14.003 GB/s
FP16 equivalent   = 49.787 GB/s
H2D/GEMV          = 15.832
stream/H2D        = 1.006
```

## 결론

실제 Q4_K decode도 거의 순수 PCIe-bound였다.

---

# 17. Granite Block 0 Mixed Tensor Streaming

파일:

```text
/mnt/data/granite_block0_stream/
```

Block 0:

```text
total weight    120.797 MiB
A/B stage       82.031 MiB
```

tensor별:

```text
attn_k    H2D 0.169 ms / GEMV 0.024 ms
attn_out  H2D 0.670 ms / GEMV 0.045 ms
attn_q    H2D 0.671 ms / GEMV 0.041 ms
attn_v    H2D 0.248 ms / GEMV 0.022 ms
down      H2D 3.048 ms / GEMV 0.144 ms
gate      H2D 2.091 ms / GEMV 0.128 ms
up        H2D 2.091 ms / GEMV 0.121 ms
```

합계:

```text
H2D sum        8.987 ms
GEMV sum       0.525 ms
streamed block 9.248 ms
payload        13.696 GB/s
```

40 blocks projection:

```text
~369.938 ms/token
~2.703 tok/s
```

---

# 18. llama.cpp Stock Baseline — Granite

Reference runner:

```text
/mnt/data/granite_reference_chat/
```

Stock llama.cpp + full GPU offload:

```text
model size 5,344,346,112 bytes
params     8,791,592,960
ctx        4096
-ngl       99
```

Prompt:

```text
대한민국의 수도는 어디인가?
```

결과:

```text
대한민국의 수도는 서울입니다.
```

성능:

```text
load        7.077 s
prompt      310.423 tok/s
generation   60.434 tok/s
```

---

# 19. Hybrid Full Linear Path Simulator

파일:

```text
/mnt/data/hybrid_full_model/
```

40 block × 7 linear tensor 총:

```text
4553.438 MiB
```

resident block 수별:

```text
8 blocks:
stream 3614.906 MiB
resident 938.531 MiB
278.094 ms/token
3.596 tok/s

16 blocks:
214.858 ms/token
4.654 tok/s

24 blocks:
150.878 ms/token
6.628 tok/s

32 blocks:
87.386 ms/token
11.443 tok/s

36 blocks:
54.823 ms/token
18.241 tok/s

38 blocks:
38.309 ms/token
26.104 tok/s

40 blocks:
21.382 ms/token
46.768 tok/s
```

관찰:

```text
T_token ≈ 21.4 ms + streamed_bytes / ~15 GB/s
```

## 결론

Dense decode는 결국:

```text
streamed bytes/token
```

이 성능을 결정한다.

---

# 20. 실제 llama.cpp RAM → VRAM 통합 — Granite

초기 probe:

```text
/mnt/data/llama_ram2vram_probe/
```

현재 checkout에서는 CUDA dispatch가:

```text
ggml/src/ggml-cuda/ggml-cuda.cu
```

에 존재했다.

실제 graph 확인:

```text
prefill:
blk0.attn_q
Q4_K [4096,4096] × F32 [4096,24]
→ F32 [4096,24]

decode:
Q4_K [4096,4096] × F32 [4096,1]
→ F32 [4096,1]
```

---

# 21. llama.cpp 실제 RAM→VRAM Weight Replacement 성공

파일:

```text
/mnt/data/llama_ram2vram_replace_attn_q_legacy/
```

실험 내용:

- Granite blk.0.attn_q.weight를 GGUF file offset에서 직접 읽음
- 9 MiB Q4_K weight를 pinned system RAM에 보관
- decode 시 CUDA stage buffer로 H2D
- custom GEMV 실행
- 기존 llama.cpp generation graph 안에서 실제 연산 대체

실행 로그:

```text
[RAM2VRAM] initialized blk.0.attn_q.weight
 host pinned ...
 stage VRAM ...
 bytes 9437184
 offset 0x22cbf2a0

[RAM2VRAM] handled legacy decode attn_q #1
[RAM2VRAM] handled legacy decode attn_q #2
```

Stock greedy output token:

```text
67945,24486,50273,120
```

Custom RAM→VRAM path output:

```text
67945,24486,50273,120
```

완전히 동일.

성능:

```text
load       7.026 s
prompt     311.155 tok/s
generation 54.310 tok/s
```

## 결론

**실제 llama.cpp decode graph에서 RAM → VRAM streamed weight op를 삽입하고 정확한 output을 유지하는 것까지 성공했다.**

즉 feasibility 자체는 증명됐다.

---

# 22. Dense Model 실험 결론

Granite 실험에서 확인한 결론:

```text
Dense decode에서 매 token마다 전체 layer weight를 RAM에서 가져오는 방식은
PCIe bandwidth 때문에 구조적으로 성능이 크게 제한된다.
```

따라서 다음 방향으로 pivot:

```text
Dense sequential streaming
        ↓
MoE selected-expert streaming
```

---

# 23. gpt-oss-120b 전환

목표 모델:

```text
ggml-org/gpt-oss-120b-GGUF
```

Model type:

```text
MXFP4 MoE
```

llama.cpp build:

```text
build b10986-6011c34ce
```

처음 Ollama model:

```text
gpt-oss:120b
SIZE ~65 GB
```

Ollama blob architecture metadata가:

```text
gptoss
```

였고 stock llama.cpp는:

```text
gpt-oss
```

를 기대하여 직접 blob 사용은 실패.

따라서 llama.cpp용 GGUF를 별도로 다운로드.

---

# 24. llama.cpp HTTPS / Build 문제

Standalone llama.cpp build 중:

```text
No CUDA toolset found
```

문제 때문에 Ninja + vcvars64 + explicit nvcc 방식 사용.

Anaconda OpenSSL include가 잡혀:

```text
bool macroized
xkeycheck.h C1189
```

오류 발생.

처음에는:

```text
-DLLAMA_OPENSSL=OFF
```

로 해결했지만 model download HTTPS가 동작하지 않음.

최종 방향:

```text
-DLLAMA_BUILD_BORINGSSL=ON
-DLLAMA_OPENSSL=OFF
```

로 HTTPS 지원.

---

# 25. gpt-oss-120b 실행 성공

실행 확인:

```text
build      : b10986-6011c34ce
model      : ggml-org/gpt-oss-120b-GGUF
ftype      : MXFP4 MoE
modalities : text
```

초기 reasoning 출력 때문에 `-n 16`에서는 final answer까지 못 가는 현상이 있었음.

Reasoning을 끄거나 token budget을 충분히 주면 정상 답변 확인.

대략 warm 상태 generation:

```text
~10 ~ 15 tok/s
```

수준 확인.

즉:

```text
64 GB RAM + RTX 5060 Ti 16 GB
```

환경에서 gpt-oss-120b 실제 실행 성공.

---

# 26. MoE Expert Routing Probe — Stage 1

현재 llama.cpp source에서 MoE 경로 검색.

CUDA 쪽 진입:

```cpp
static void ggml_cuda_mul_mat_id(
    ggml_backend_cuda_context & ctx,
    ggml_tensor * dst)
```

구조:

```cpp
const ggml_tensor * src0 = dst->src[0];
const ggml_tensor * src1 = dst->src[1];
const ggml_tensor * ids  = dst->src[2];
```

fast-path:

```text
MMVQ / MMVF
```

를 사용하며 decode에서는 함수 초반에서 return할 수 있음.

따라서 CUDA probe는 fast path 전에 넣어야 한다.

---

# 27. CUDA MoE Probe가 안 뜬 이유

CUDA `ggml_cuda_mul_mat_id()`에 probe를 넣었지만 로그가 전혀 발생하지 않음.

원인:

```text
gpt-oss-120b expert MUL_MAT_ID가 현재 16 GB VRAM 구성에서
CPU backend에 배치되어 실행 중
```

CPU 경로 검색 결과:

```text
ggml/src/ggml-cpu/ggml-cpu.c

ggml_compute_forward_mul_mat_id()
```

---

# 28. CPU MoE Expert ID Probe

CPU `ggml_compute_forward_mul_mat_id()`에 probe 삽입.

중요 수정:

CPU worker thread들이 동시에 같은 op를 실행하므로 probe를 모든 thread에서 호출하면:

```text
call=0
call=1
call=3
call=2
...
```

처럼 race와 중복 logging이 발생.

따라서:

```c
if (params->ith == 0) {
    ram2vram_cpu_probe_moe_ids(src0, src1, ids, dst);
}
```

처럼 worker 0 하나만 logging.

CSV 개행 문제도 발견:

잘못된:

```c
"\\n"
```

이 literal `\n`으로 저장됨.

수정:

```c
"\n"
```

---

# 29. gpt-oss MoE 구조 실제 확인

실제 로그:

```text
blk.7  experts = [1, 19, 88, 43]
blk.8  experts = [126, 66, 14, 76]
blk.9  experts = [27, 64, 60, 46]
blk.10 experts = [97, 72, 60, 23]
...
```

각 layer:

```text
total experts = 128
selected experts/token = 4
```

또한 한 routing decision의 같은 expert set을:

```text
ffn_gate_exps
ffn_up_exps
ffn_down_exps
```

세 tensor가 공유함.

즉:

```text
gate / up / down
```

을 하나의 expert bundle로 보는 것이 적절하다.

---

# 30. 46-token MoE Locality 측정

첫 trace:

```text
raw MMID calls         4000
collapsed route events 1334
layers                 29
experts/event          4
```

대략:

```text
1334 / 29 ≈ 46 decode token
```

Per-layer LRU:

```text
cache  2/layer  4.67%
cache  4/layer 35.08%
cache  8/layer 57.68%
cache 16/layer 73.39%
cache 32/layer 79.14%
cache 64/layer 79.37%
```

Unique expert:

```text
min 26
avg 37.97
max 52
```

관찰:

```text
cache32 ≈ cache64
```

즉 짧은 trace에서는 32 experts/layer 정도면 거의 available locality를 다 잡았다.

---

# 31. 127-token MoE Locality 최종 측정

Probe limit:

```text
12000
```

으로 확대.

결과:

```text
raw MMID calls         11049
collapsed route events 3683
layers seen            29
expert IDs/event       4
```

토큰 수:

```text
3683 / 29
= 127 decode token
```

즉 사실상 128-token 전체 decode trace.

## Per-layer LRU cache hit rate

```text
cache  2/layer :  5.28%
cache  4/layer : 40.30%
cache  8/layer : 64.15%
cache 16/layer : 79.34%
cache 32/layer : 87.71%
cache 64/layer : 89.99%
```

## Unique experts touched

```text
min/layer : 34
avg/layer : 50.79
max/layer : 72
```

---

# 32. MoE Locality 결과 해석

한 layer당:

```text
127 tokens × 4 experts
= 508 expert accesses
```

평균 unique experts:

```text
50.79
```

따라서 compulsory miss를 제외한 theoretical maximum cache hit:

```text
1 - 50.79 / 508
≈ 90.0%
```

실제:

```text
cache64/layer = 89.99%
```

와 거의 정확히 일치.

즉 `cache64`에서 남는 miss는 대부분:

```text
처음 보는 expert
```

이며 cache policy 문제가 아니다.

또:

```text
cache32 87.71%
cache64 89.99%
```

차이는:

```text
+2.28 percentage points
```

뿐이다.

## 현재 locality 관점의 sweet spot

대략:

```text
16 ~ 32 experts/layer
```

범위에서 효율이 좋다.

하지만 이 결과를 그대로 실제 VRAM 구조에 적용할 수는 없다.

예:

```text
29 layers × 32 experts
= 928 expert bundles
```

로 16 GB VRAM에 들어갈 수 없기 때문이다.

---

# 33. 현재까지 얻은 가장 중요한 결론

## Dense model

```text
전체 layer weight streaming
→ decode에서 PCIe-bound
→ 실용성이 낮음
```

Granite에서 실제로 검증됨.

## MoE model

gpt-oss-120b에서:

```text
128 experts/layer
중 4 experts/token만 활성화
```

그리고 127-token trace 기준으로:

```text
실제 expert locality 존재
cache16/layer → 79.34%
cache32/layer → 87.71%
```

를 확인.

즉 MoE에서는:

```text
router-selected expert
+ VRAM expert cache
+ cache miss 시 RAM → VRAM transfer
```

구조가 dense model보다 훨씬 가능성이 높다.

---

# 34. 현재 시스템 관점의 중요 수치

CPU MoE layer:

```text
blk.7 ~ blk.35
= 29 layers
```

한 token당 expert selection:

```text
29 layers × 4 experts
= 116 expert selections/token
```

이상적으로 cache hit가:

### 80%

```text
116 × 0.20
≈ 23.2 expert misses/token
```

### 90%

```text
116 × 0.10
≈ 11.6 expert misses/token
```

즉 다음 핵심 변수는:

```text
expert 하나의 실제 byte size
```

다.

---

# 35. 다음 작업

이제 per-layer locality 실험은 충분히 끝났다.

다음 단계는 **실제 VRAM budget 기반 simulation**이다.

## Step 1. gpt-oss GGUF Expert Tensor Size 측정

layer별:

```text
ffn_gate_exps
ffn_up_exps
ffn_down_exps
```

에서 expert 하나가 차지하는 byte를 계산.

```text
expert bundle bytes
=
gate expert bytes
+ up expert bytes
+ down expert bytes
```

---

## Step 2. 실제 VRAM Budget 계산

RTX 5060 Ti 16 GB에서:

```text
16 GB
- resident non-expert weights
- KV cache
- CUDA workspace / scratch
- existing GPU layers
-----------------------------
available expert-cache VRAM
```

계산.

---

## Step 3. Global Cache Simulator

현재 per-layer cache는 unrealistic.

다음에는 실제 `(layer, expert)`를 하나의 cache key로 사용.

예:

```text
(blk.7, expert 1)
(blk.12, expert 88)
...
```

그리고 전체 VRAM budget을:

```text
2 GB
4 GB
6 GB
8 GB
...
```

로 나누어 global LRU / LFU / hybrid cache simulation.

측정할 것:

```text
cache hit rate
misses/token
MB transferred/token
PCIe ms/token
estimated tok/s
```

---

## Step 4. 실제 Expert Streaming Runtime

simulation 결과가 충분히 좋으면:

```text
router output
    ↓
selected expert IDs
    ↓
global VRAM expert cache lookup
    ↓
hit → GPU resident expert 사용
miss → pinned RAM → VRAM async H2D
    ↓
gate / up / down GPU execution
    ↓
LRU / LFU metadata update
```

구현.

---

# 36. 현재 프로젝트 상태 요약

현재까지 다음을 실제로 검증했다.

- PCIe 4.0 x8 실효 H2D 약 14.3 GB/s
- CUDA copy/compute overlap 약 90~100%
- Q4/Q3/Q2 compression streaming
- custom fused quantized GPU kernels
- 실제 Granite GGUF Q4_K weight 처리
- 실제 llama.cpp decode graph에 RAM→VRAM streamed op 삽입
- stock과 custom path의 output token 일치
- Dense decode streaming의 PCIe bottleneck 실증
- gpt-oss-120b를 64GB RAM + 16GB VRAM 환경에서 실제 실행
- gpt-oss-120b MoE expert routing probe 성공
- 실제 top-4 / 128 expert 구조 확인
- 127-token expert locality trace 확보
- per-layer cache16 = 79.34%
- per-layer cache32 = 87.71%
- per-layer cache64 = 89.99%
- MoE expert cache / streaming을 계속 실험할 충분한 근거 확보

---

# 37. 현재 결론

이 프로젝트의 방향은 다음처럼 정리할 수 있다.

```text
초기 아이디어
RAM 전체 weight
→ layer 단위 VRAM streaming

        ↓

Dense Granite 실제 검증
→ decode에서는 PCIe 때문에 비효율

        ↓

MoE gpt-oss-120b 전환
→ token마다 일부 expert만 활성

        ↓

실제 expert routing 측정
→ temporal locality 확인

        ↓

다음 목표
VRAM global expert cache
+ cache miss expert만 RAM→VRAM streaming
```

따라서 현재 가장 유망한 최종 구조는:

```text
PCIe-aware MoE Expert Cache Runtime
```

이다.

단순한 CPU offload와 다른 점은:

- 필요한 expert만 전송
- quantized form 그대로 전송
- pinned RAM 사용
- async H2D
- expert cache hit 활용
- gate/up/down bundle 단위 관리
- GPU에서 실제 MoE expert compute 수행
- bytes/token과 exposed transfer stall을 최소화

하는 데 있다.
