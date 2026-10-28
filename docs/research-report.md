# PCIe-Aware MoE Expert Cache 기반 대형 LLM 로컬 추론 최적화 연구 보고서

작성일: 2026-09-19

---

## 공개 데이터와 코드

- Routing traces: [`research/data/traces/`](../research/data/traces/)
- Global cache simulation: [`research/global-cache/`](../research/global-cache/)
- VRAM allocation optimizer: [`research/optimizer/`](../research/optimizer/)
- Probe instrumentation: [`research/probes/`](../research/probes/)
- Compact benchmark results: [`research/results/benchmark-summary.csv`](../research/results/benchmark-summary.csv)

원본 실행 로그에는 로컬 절대 경로가 포함되어 있어 공개하지 않고, 위 요약 CSV에 측정값과 로컬 근거 파일명을 기록하였다.

---

# 초록

본 연구는 **16GB VRAM을 가진 소비자용 GPU와 64GB 시스템 RAM 환경에서 120B급 대형 언어 모델을 실용적인 속도로 실행하기 위한 RAM↔VRAM 스트리밍 및 MoE expert cache 최적화 방법**을 실험적으로 검증한 것이다.

초기에는 dense LLM의 weight를 system RAM에 두고, 각 layer에 필요한 weight를 PCIe를 통해 GPU로 스트리밍하면서 compute와 copy를 overlap하는 방식을 검토하였다. CUDA pinned memory, asynchronous H2D, double buffering, quantized transport, fused dequantization, custom GEMV/GEMM kernel 등을 단계적으로 구현하고 측정한 결과, dense decode에서는 weight transfer 비용이 연산 비용보다 압도적으로 커서 PCIe bandwidth가 구조적 병목이 됨을 확인하였다.

이후 연구 방향을 Mixture-of-Experts(MoE) 모델인 **gpt-oss-120b**로 전환하였다. 실제 llama.cpp 실행 경로에 probe를 삽입하여 router가 각 layer에서 128개의 expert 중 4개만 선택한다는 점을 확인하고, 127-token routing trace를 수집하여 expert temporal locality를 정량화하였다. 그 결과 per-layer LRU 기준으로 cache 16개에서 79.34%, 32개에서 87.71%, 64개에서 89.99%의 hit rate를 관찰하였다.

GGUF tensor 구조를 직접 분석한 결과 expert bundle 하나의 크기는 12.607 MiB였으며, 전체 expert tensor는 약 56.731 GiB였다. 16GB VRAM 환경에서 static layer residency와 global expert cache 전략을 비교한 결과, full-layer 고정 상주보다 global cache가 대부분의 VRAM budget 구간에서 더 효율적이었다.

여러 expert cache 구현을 실제 llama.cpp에 적용한 결과, persistent slot remap 방식은 8.2 tok/s baseline 대비 3.1~3.3 tok/s로 오히려 성능이 크게 저하되었다. 반면 hybrid expert cache 방식은 cache OFF 6.6 tok/s에서 8GiB cache 적용 시 7.5 tok/s로 개선되었고, 실제 대화형 llama-server 환경에서는 약 **19~20 tok/s** 수준의 안정적인 generation throughput을 확인하였다.

본 연구의 핵심 결론은 다음과 같다.

> 16GB VRAM 환경에서 120B급 MoE 모델을 실행하는 것 자체는 기존 llama.cpp CPU-MoE offload로 가능하지만, 실질적인 성능 향상은 **반복적으로 선택되는 expert의 PCIe 전송을 줄이는 VRAM-resident expert cache**에서 발생한다.

---

# 1. 연구 배경

대형 언어 모델의 parameter 수가 증가함에 따라 일반적인 소비자용 GPU의 VRAM만으로 전체 model weight를 상주시킬 수 없는 경우가 많다.

본 연구 환경의 GPU는 NVIDIA GeForce RTX 5060 Ti 16GB이며, gpt-oss-120b GGUF model의 실제 파일 크기는 약 59GB이다. 따라서 전체 weight를 GPU에 적재하는 것은 불가능하다.

일반적인 해결 방법은 다음과 같다.

1. CPU RAM에 일부 weight를 유지
2. GPU에 들어가는 layer만 offload
3. CPU와 GPU가 나누어 inference 수행
4. 필요한 tensor를 host↔device 간 이동

그러나 이러한 방식의 성능은 PCIe bandwidth에 크게 영향을 받는다.

본 연구에서는 이 문제를 다음 질문으로 정의하였다.

> 대형 LLM의 대부분 weight를 RAM에 두고, 필요한 weight 또는 expert만 GPU로 선택적으로 전송하면서 VRAM cache를 활용하면 CPU offload보다 더 높은 decode throughput을 얻을 수 있는가?

---

# 2. 연구 목표

본 연구의 목표는 다음과 같다.

- PCIe 4.0 x8 환경의 실효 H2D bandwidth 측정
- CUDA copy/compute overlap 가능성 검증
- quantized weight streaming 성능 측정
- dense LLM decode에서 RAM→VRAM streaming의 구조적 한계 확인
- 실제 llama.cpp inference graph에 RAM→VRAM weight replacement 삽입
- gpt-oss-120b MoE expert routing 분석
- expert locality 및 cache hit potential 정량화
- 실제 expert byte size와 VRAM budget 기반 global cache simulation
- static full-layer residency와 global expert cache 비교
- 실제 llama.cpp runtime에서 expert cache 구현 성능 측정
- 최종적으로 실제 대화 가능한 gpt-oss-120b local chat 환경 구축

---

# 3. 실험 환경

## 3.1 Hardware

- CPU: AMD Ryzen 5 5600X
- Cores / Threads: 6C / 12T
- GPU: RTX 5060 Ti 16GB
- VRAM: 16GB
- System RAM: 64GB
- GPU Compute Capability: 12.0
- SM count: 36
- asyncEngineCount: 1
- Concurrent kernel execution: supported

## 3.2 PCIe

- GPU capability: PCIe Gen5
- Host maximum: PCIe Gen4
- Link width: x8
- Idle 상태에서는 power saving으로 Gen2 표시
- 실제 load 환경에서는 PCIe 4.0 x8 수준의 throughput 확인

## 3.3 Software

- Windows
- CUDA Toolkit 12.8
- nvcc 12.8.61
- Visual Studio 2022 Community
- MSVC 19.43
- llama.cpp 여러 experimental build 사용
- gpt-oss-120b GGUF
- Granite 4.1 8B GGUF

---

# 4. 연구 방법론 개요

전체 연구는 다음 네 단계로 진행하였다.

## Phase 1. PCIe 및 CUDA 기본 특성 측정

- pinned memory
- H2D bandwidth
- asynchronous transfer
- copy/compute overlap
- double buffering

## Phase 2. Dense LLM streaming 검증

- FP16 weight streaming
- Q4/Q3/Q2 transport
- fused dequantization
- custom GEMV/GEMM
- 실제 Granite GGUF tensor 사용
- 실제 llama.cpp decode graph에 RAM→VRAM weight 삽입

## Phase 3. MoE 전환

- gpt-oss-120b 실행
- MUL_MAT_ID routing path 분석
- CPU/CUDA expert routing probe
- 127-token expert routing trace 수집
- expert locality 측정
- 실제 expert byte size 계산
- global expert cache simulation

## Phase 4. 실제 expert cache runtime

- persistent expert slot pool 테스트
- hybrid expert cache 테스트
- llama-server 기반 실제 대화 테스트
- end-to-end generation throughput 측정

---

# 5. PCIe H2D Bandwidth 측정

Pinned host memory 기반 H2D copy를 측정하였다.

## 결과

```text
1024 MiB × 20  ≈ 14.28 GB/s
2048 MiB × 30  ≈ 14.27 GB/s
Write Combined ≈ 14.25 GB/s
Multiple H2D streams ≈ 유의미한 개선 없음
```

## 결론

실효 H2D bandwidth는 약:

```text
14.1 ~ 14.3 GB/s
```

였다.

이는 PCIe 4.0 x8 practical bandwidth에 매우 근접한 값이다.

따라서 이후 최적화에서 중요한 것은 raw bandwidth 향상이 아니라 다음 세 가지였다.

```text
1. 전송해야 하는 byte 자체 감소
2. compute와 copy overlap
3. cache hit를 통한 transfer 회피
```

---

# 6. CUDA Copy / Compute Overlap

512MiB synthetic workload에서 H2D와 compute를 동시에 실행하였다.

```text
copy       37.805 ms
compute    35.213 ms
sequential 72.842 ms
concurrent 38.820 ms

overlap efficiency 97.118%
speedup            1.876x
```

cuBLAS GEMM에서도 약 92~100% 수준의 overlap이 관찰되었다.

## 결론

CUDA runtime 자체는 H2D와 compute overlap이 충분히 가능하였다.

따라서 이후 성능의 핵심은 scheduling overhead보다 **전송량 자체**였다.

---

# 7. Dense Weight Streaming 실험

## 7.1 FP16 A/B Double Buffer

4096×4096 FP16 matrix는 layer당 약 32MiB이다.

```text
sequential 4.057 ms/layer
streaming  2.397 ms/layer
417.1 layers/s
effective H2D 13.996 GB/s
speedup 1.692x
```

성능은 사실상 PCIe bandwidth로 제한되었다.

---

# 8. Quantized Transport 실험

## 8.1 Q4 Transport + Dequant + GEMM

32MiB FP16 weight를 8MiB Q4 형태로 전송하였다.

```text
Q4 H2D   0.598 ms
dequant  0.120 ms
GEMM     1.534 ms
stream   1.722 ms
```

compression으로 H2D가 compute보다 작아질 수 있음을 확인하였다.

---

# 9. Fused Q4 Kernel

Q4Block32:

```cpp
struct Q4Block32 {
    __half scale;
    uint8_t qs[16];
};
```

약 4.5 bit/weight.

결과:

```text
H2D       0.674 ms
fused     0.867 ms
streaming 1.276 ms
```

이후 multi-warp kernel 최적화를 통해 compute가 크게 개선되었다.

---

# 10. Multi-warp Q4 Kernel

Single warp:

```text
fused  0.913 ms
stream 1.159 ms
```

4-warp / 128-thread version:

```text
fused  0.447 ms
stream 0.710 ms
```

```text
fused speedup     2.045x
streaming speedup 1.634x
```

Kernel compute가 빨라지자 다시 PCIe가 bottleneck으로 나타났다.

---

# 11. Q4 / Q3 / Q2 비교

```text
Q4:
H2D    0.670 ms
compute 0.455 ms
H2D/compute = 1.471

Q3:
H2D    0.521 ms
compute 0.478 ms
H2D/compute = 1.09

Q2:
H2D    0.373 ms
compute 0.443 ms
H2D/compute = 0.842
```

Prefill-style workload에서는 Q2 정도까지 줄이면 PCIe 병목을 벗어날 수 있었다.

---

# 12. Decode GEMV 실험

Batch 1:

```text
Q4 H2D 0.671 ms / GEMV 0.039 ms
Q3 H2D 0.523 ms / GEMV 0.066 ms
Q2 H2D 0.375 ms / GEMV 0.040 ms
```

## 결론

Decode에서는 compute보다 H2D가 압도적으로 크다.

Dense model에서 매 token마다 전체 weight를 streaming하는 방식은 구조적으로 비효율적이었다.

---

# 13. Granite 4.1 8B 실제 GGUF 분석

Granite GGUF의 주요 block tensor는 다음과 같았다.

```text
attn_k      2.25 MiB
attn_output 9 MiB
attn_q      9 MiB
attn_v      3.28 MiB
ffn_down    41.016 MiB
ffn_gate    28.125 MiB
ffn_up      28.125 MiB
```

Block 0 전체 주요 linear tensor는 약 120.797MiB였다.

---

# 14. 실제 Granite Q4_K GEMV

실제:

```text
blk.0.attn_q.weight
9 MiB
Q4_K
```

정확도:

```text
max abs error = 7e-8
relative error = 8.9e-7
PASS
```

성능:

```text
H2D       0.670 ms
GEMV      0.042 ms
A/B stream 0.674 ms
```

즉 실제 GGUF tensor에서도 decode는 거의 순수 PCIe bound였다.

---

# 15. Granite Full Block Streaming Projection

Block 0 mixed tensor:

```text
H2D sum        8.987 ms
GEMV sum       0.525 ms
streamed block 9.248 ms
```

40 blocks projection:

```text
≈369.938 ms/token
≈2.703 tok/s
```

## 결론

Dense model 전체 weight streaming은 실용적이지 않았다.

---

# 16. 실제 llama.cpp RAM→VRAM Weight Replacement

실제 llama.cpp CUDA graph에서:

```text
blk.0.attn_q.weight
```

를 intercept하여 다음 구조를 구현하였다.

```text
GGUF file
→ pinned system RAM
→ CUDA stage buffer
→ custom GEMV
→ llama.cpp output
```

Stock greedy output token:

```text
67945, 24486, 50273, 120
```

Custom RAM→VRAM path:

```text
67945, 24486, 50273, 120
```

완전히 동일하였다.

## 의미

RAM→VRAM streamed weight를 실제 llama.cpp decode graph에 삽입해도 정확한 model output을 유지할 수 있음을 검증하였다.

---

# 17. Dense Model 실험의 최종 결론

Dense model에서는 다음 근사식이 지배적이었다.

```text
T_token ≈ resident_compute_floor + streamed_bytes / PCIe_bandwidth
```

실측상 PCIe bandwidth는 약 14~15GB/s였으므로, dense decode의 성능은 거의 streamed bytes/token으로 결정되었다.

따라서 연구 방향을 MoE로 전환하였다.

---

# 18. gpt-oss-120b 전환

사용 모델:

```text
ggml-org/gpt-oss-120b-GGUF
```

실제 GGUF blob:

```text
63,387,346,208 bytes
≈ 59 GiB
```

Model type:

```text
MXFP4 MoE
```

본 모델은 128 experts/layer 구조이며 실제 router는 token당 top-4 expert를 선택하였다.

---

# 19. gpt-oss-120b 기본 실행

64GB RAM + 16GB VRAM 환경에서 llama.cpp를 통해 기본 실행에 성공하였다.

즉 본 연구의 성과는 "120B 모델을 실행 가능하게 만든 것" 자체가 아니다.

기존 llama.cpp CPU-MoE offload만으로도 실행 가능하였다.

본 연구의 실제 목표는:

> CPU RAM에 있는 expert를 반복적으로 PCIe로 전송하는 비용을 줄여 decode throughput을 높이는 것

이었다.

---

# 20. MoE Routing Probe

CUDA `MUL_MAT_ID` path를 probe하였으나 일부 MoE 연산이 CPU backend에 위치해 있어 CUDA probe가 발생하지 않는 것을 확인하였다.

CPU:

```text
ggml_compute_forward_mul_mat_id()
```

경로를 probe하였다.

CPU worker thread 중복 logging을 방지하기 위해:

```cpp
if (params->ith == 0) {
    probe(...);
}
```

형태로 수정하였다.

---

# 21. 실제 Expert Routing 결과

각 layer에서 128 expert 중 4개가 선택되었다.

예:

```text
blk.7  [1, 19, 88, 43]
blk.8  [126, 66, 14, 76]
blk.9  [27, 64, 60, 46]
blk.10 [97, 72, 60, 23]
```

gate/up/down 세 tensor가 같은 routing result를 사용하므로 이를 하나의 expert bundle로 정의하였다.

---

# 22. 127-token Expert Locality Trace

수집 결과:

```text
raw MMID calls         : 11049
collapsed route events : 3683
layers seen            : 29
expert IDs/event       : 4
```

```text
3683 / 29 = 127 decode token steps
```

Per-layer LRU hit rate:

```text
cache  2/layer :  5.28%
cache  4/layer : 40.30%
cache  8/layer : 64.15%
cache 16/layer : 79.34%
cache 32/layer : 87.71%
cache 64/layer : 89.99%
```

Unique experts:

```text
min/layer : 34
avg/layer : 50.79
max/layer : 72
```

---

# 23. Expert Locality 해석

한 layer당:

```text
127 tokens × 4 experts
= 508 expert accesses
```

평균 unique expert:

```text
50.79
```

이론적 compulsory-miss limit:

```text
1 - 50.79 / 508
≈ 90%
```

실제 cache64 hit rate:

```text
89.99%
```

와 거의 동일했다.

## 결론

expert routing에는 명확한 temporal locality가 존재하였다.

---

# 24. 실제 Expert Bundle Size

GGUF tensor span을 직접 분석하였다.

결과:

```text
avg expert bundle        : 12.607 MiB
min/max bundle           : 12.607 / 12.607 MiB
all expert tensors       : 56.731 GiB
```

즉 모델 전체 약 59GiB 중 대부분이 MoE expert weight였다.

expert bundle:

```text
ffn_gate_exps
+ ffn_up_exps
+ ffn_down_exps
```

한 expert 기준:

```text
12.607 MiB
```

---

# 25. Cache 없는 경우의 PCIe 비용

36 layer × top-4 기준:

```text
144 expert accesses/token
```

expert 하나:

```text
12.607 MiB
```

전부 miss일 경우:

```text
144 × 12.607 MiB
≈ 1.77 GiB/token
```

PCIe 14.2GB/s 기준으로 100ms 이상이 필요하다.

따라서 cache 없이 expert를 매번 streaming하면 decode throughput은 PCIe에 강하게 제한된다.

---

# 26. Global Expert Cache Simulation

29-layer trace 기준:

```text
0.5 GiB : hit 0%
1.0 GiB : hit 0%
2.0 GiB : hit 49.84%
3.0 GiB : hit 65.49%
4.0 GiB : hit 73.24%
5.0 GiB : hit 77.63%
6.0 GiB : hit 80.70%
7.0 GiB : hit 83.46%
8.0 GiB : hit 84.79%
10 GiB  : hit 87.68%
12 GiB  : hit 88.66%
```

8GiB cache 기준:

```text
misses/token   : 17.65
transfer/token : 222.46 MiB
PCIe time      : 16.427 ms/token
```

---

# 27. Global LRU Working Set 특성

1GiB cache에서는 hit가 0%였다.

이유:

```text
29 layers × 4 experts
= 116 expert entries/token
```

1GiB cache는 약 81 expert bundle만 저장 가능하다.

따라서 다음 token이 같은 layer로 돌아오기 전에 이전 token의 expert가 모두 eviction되었다.

2GiB부터 162 entries가 가능해져 working set보다 커지고 hit rate가 급격히 증가하였다.

---

# 28. 36-layer Full Routing Trace

`--cpu-moe`를 사용해 모든 MoE layer를 CPU path로 강제하여 전체 routing trace를 확보하였다.

결과:

```text
layers in trace       : 36
decode steps inferred : 55
expert bundle avg     : 12.607 MiB
full expert layer     : 1.576 GiB
```

---

# 29. Static Layer Residency vs Global Cache

동일 VRAM budget에서 비교하였다.

## 4GiB

```text
GLOBAL-LRU
hit=66.30%
611.77 MiB/token
45.175 ms/token

BEST PREFIX
pin 1 layer
908.61 MiB/token
67.095 ms/token
```

Global cache가 명확히 우세했다.

## 8GiB

```text
GLOBAL-LRU
384.62 MiB/token
28.402 ms/token

BEST PREFIX
407.09 MiB/token
30.061 ms/token
```

역시 global cache가 우세했다.

## 10GiB

```text
GLOBAL-LRU
364.22 MiB/token
26.895 ms/token

pin 1 full layer
355.74 MiB/token
26.269 ms/token
```

차이는 매우 작았다.

## 12GiB

```text
GLOBAL-LRU
336.03 MiB/token
24.814 ms/token

pin 2 full layers
334.65 MiB/token
24.712 ms/token
```

거의 동일하였다.

## 결론

16GB GPU에서 full expert layer를 고정 상주시키는 전략은 대부분의 budget 구간에서 global dynamic cache보다 비효율적이었다.

---

# 30. Persistent Expert Slot Pool 실험

별도의 persistent MoE expert pool implementation을 실제 llama.cpp에 적용하였다.

Baseline:

```text
mec 0
Generation ≈ 8.2 tok/s
```

Cache 적용:

```text
mec 8  ≈ 3.3 tok/s
mec 12 ≈ 3.2 tok/s
mec 16 ≈ 3.1 tok/s
```

## 결론

Cache capacity가 증가해도 성능이 회복되지 않았다.

따라서 병목은 cache hit rate가 아니라 다음과 같은 runtime overhead에 있다고 판단하였다.

- expert ID remapping
- synchronization
- slot management
- cache update
- readback
- remap bookkeeping
- potential Windows/WDDM overhead

이 구현 방식은 본 환경에서 폐기하였다.

---

# 31. Hybrid Expert Cache 적용

다음으로 slot remap 대신 hybrid execution 방식의 MoE cache를 적용하였다.

개념:

```text
router-selected expert
        |
        +-- cache hit
        |     -> GPU resident expert compute
        |
        +-- cache miss
              -> 기존 selective-copy / host path
```

Baseline:

```text
cache OFF
Generation 6.6 tok/s
```

8GiB hybrid cache:

```text
Generation 7.5 tok/s
```

약:

```text
+13.6%
```

의 개선이 관찰되었다.

---

# 32. 실제 대화형 서버 적용

Hybrid cache를 llama-server 형태로 실행하였다.

설정 개요:

```text
gpt-oss-120b
-ngl 99
--cpu-moe
--moe-cache 8192
context 4096
reasoning off
```

실제 대화형 로그:

```text
n_decoded = 100
tg = 19.49 t/s
```

최종:

```text
eval time = 7953.31 ms / 158 tokens
50.34 ms/token
19.87 tokens/s
```

Prompt:

```text
2243.41 ms / 44 tokens
19.61 tokens/s
```

Total:

```text
10196.72 ms / 202 tokens
```

---

# 33. Prefix / Context Reuse

로그:

```text
selected slot by LCP similarity
f_sim_best = 0.807
f_keep = 0.825
```

이는 이전 conversation context의 약 82.5%를 재사용한 것으로 해석할 수 있다.

또한:

```text
graphs reused = 293
```

으로 graph reuse도 정상적으로 동작하였다.

따라서 실제 대화 환경에서 context history 전체를 매번 처음부터 재계산하지 않고 prefix/KV reuse가 적용되고 있었다.

---

# 34. 최종 실사용 성능

최종적으로 확인된 환경:

```text
Model:
gpt-oss-120b
MXFP4 MoE
≈59 GiB GGUF

Hardware:
RTX 5060 Ti 16GB
RAM 64GB
Ryzen 5 5600X

Runtime:
llama.cpp
CPU-MoE
Hybrid MoE expert cache ≈8GiB

Observed decode:
≈19.5 ~ 19.9 tok/s
```

이는 실제 대화형 사용에서 충분히 실용적인 수준이었다.

---

# 35. 기존 llama.cpp와의 차이

중요한 점은 다음과 같다.

## 기존에도 가능했던 것

```text
16GB VRAM + 64GB RAM
→ gpt-oss-120b 실행
```

자체는 llama.cpp CPU-MoE offload로 가능했다.

따라서 본 연구의 신규성은 "120B 실행 가능 여부"가 아니다.

## 본 연구에서 검증한 핵심

```text
기존:
CPU RAM expert
→ router selection
→ 반복적인 selective H2D copy

개선:
CPU RAM expert backing store
→ router selection
→ VRAM expert cache lookup
→ hit는 resident weight 재사용
→ miss만 RAM→VRAM
```

즉 반복적인 PCIe transfer를 cache locality로 줄이는 것이 핵심이다.

---

# 36. 실패한 접근과 학습

## 36.1 Dense Full Weight Streaming

실패 이유:

```text
decode compute << H2D transfer
```

따라서 PCIe bottleneck이 너무 컸다.

## 36.2 Full Layer Residency

한 layer 전체 expert를 VRAM에 넣으면 약:

```text
1.576 GiB
```

가 필요하다.

128 expert 중 실제 사용은 top-4뿐이므로 VRAM 효율이 낮았다.

## 36.3 Persistent Slot Remap Pool

Cache 자체보다 slot remap 및 synchronization overhead가 더 커져 성능이 급락하였다.

## 36.4 단순 LRU만으로 해결되지 않는 부분

Cache hit rate가 높아져도:

- GPU compute
- routing
- CPU scheduling
- H2D synchronization
- host readback
- Windows WDDM overhead

등이 남아 있어 end-to-end throughput은 단순 PCIe upper bound보다 낮았다.

---

# 37. 성공한 접근

가장 유효했던 구조는:

```text
MoE model
+
CPU-resident expert backing store
+
VRAM hot-expert cache
+
selective copy
+
prefix/KV reuse
```

였다.

특히 MoE의 다음 특성이 결정적이었다.

```text
128 experts
top-4 selection
temporal locality 존재
```

Dense model과 달리 token당 전체 FFN weight를 사용하지 않기 때문에 cache가 실제로 의미 있는 transfer reduction을 만들 수 있었다.

---

# 38. 핵심 정량 결과 요약

| 항목 | 결과 |
|---|---:|
| PCIe H2D 실효 bandwidth | 약 14.1~14.3 GB/s |
| Granite Q4_K 9MiB H2D | 약 0.67 ms |
| Dense Granite projected decode | 약 2.7 tok/s |
| gpt-oss expert bundle | 12.607 MiB |
| 전체 expert tensor | 56.731 GiB |
| Experts / layer | 128 |
| Active experts / token / layer | 4 |
| Per-layer cache16 hit | 79.34% |
| Per-layer cache32 hit | 87.71% |
| Per-layer cache64 hit | 89.99% |
| Global cache 8GiB hit (29-layer trace) | 84.79% |
| Slot-remap cache | 성능 하락 |
| Hybrid cache OFF | 약 6.6 tok/s |
| Hybrid 8GiB benchmark | 약 7.5 tok/s |
| 실제 대화형 decode | 약 19.5~19.9 tok/s |

---

# 39. 연구의 핵심 결론

본 연구를 통해 다음을 확인하였다.

## 1. Dense LLM의 full weight streaming은 PCIe-bound이다

Quantization과 overlap을 적용하더라도 decode에서 H2D가 compute보다 훨씬 크다.

따라서 dense model 전체 weight를 매 token streaming하는 방식은 실용성이 낮다.

## 2. MoE는 구조적으로 RAM↔VRAM streaming에 더 적합하다

Top-k routing 덕분에 전체 expert 중 일부만 사용된다.

## 3. Expert routing에는 locality가 존재한다

127-token trace에서 cache32/layer가 약 87.7% hit rate를 보였다.

## 4. Full layer residency보다 dynamic expert cache가 VRAM 효율이 좋다

4~8GiB budget에서는 global cache가 static prefix residency보다 확실히 우수했다.

## 5. Cache implementation 방식이 중요하다

단순 persistent slot pool은 cache가 있어도 runtime overhead 때문에 오히려 느려질 수 있다.

## 6. Hybrid cache는 실제 end-to-end 개선 가능성이 있다

실제 대화형 llama-server에서 약 20 tok/s 수준의 throughput을 확인하였다.

---

# 40. 연구의 한계

본 연구에는 다음 한계가 있다.

## Trace length

36-layer full trace는 약 55 decode step 기준이었다.

더 긴 200~500 token trace에서 locality가 어떻게 변하는지 추가 확인이 필요하다.

## Prompt dependence

Expert routing은 prompt/domain에 따라 달라질 수 있다.

코드, 한국어, 영어, reasoning-heavy prompt 등 다양한 workload에서 재검증이 필요하다.

## Windows / WDDM

Windows 환경에서는 CUDA allocation, pageable/pinned memory, VRAM oversubscription 시 Linux와 다른 성능 특성이 발생할 수 있다.

## Cache runtime instrumentation 부족

최종 hybrid runtime에서:

```text
cache hit path
cache miss path
H2D copy
expert compute
synchronization
```

각각의 상세 시간은 아직 완전히 분해하지 않았다.

---

# 41. 후속 연구 방향

## 41.1 Cache policy 최적화

- LRU
- LFU
- Layer-aware LRU
- 2Q
- TinyLFU
- router probability 기반 admission
- expert co-occurrence 기반 prefetch

## 41.2 Async Expert Prefetch

현재 layer의 compute 중 다음 layer router output을 이용해 expert를 미리 H2D.

```text
Layer N compute
+
Layer N+1 expert prefetch
```

가 가능하면 exposed PCIe stall을 줄일 수 있다.

## 41.3 Router Probability 활용

단순 선택 expert ID뿐 아니라 router score를 활용하여 다음 token에서도 재사용 가능성이 높은 expert를 cache에 유지.

## 41.4 Expert Bundle Layout 개선

gate/up/down을 별도 tensor로 관리하기보다 bundle 단위 contiguous backing layout으로 구성하면:

```text
H2D launch 횟수 감소
metadata 감소
coalesced copy
```

가능성이 있다.

## 41.5 Longer Context 테스트

- 4K
- 8K
- 16K

context에서 KV cache 증가가 expert cache VRAM budget에 미치는 영향을 측정해야 한다.

## 41.6 Linux 비교

같은 hardware에서 Windows/WDDM과 Linux CUDA runtime 성능 차이를 비교할 가치가 있다.

---

# 42. 최종 아키텍처 제안

본 연구 결과를 기반으로 가장 합리적인 architecture는 다음과 같다.

```text
                   ┌───────────────────────────┐
                   │       System RAM          │
                   │                           │
                   │  Full MoE Expert Weights │
                   │      ~56.7 GiB            │
                   └────────────┬──────────────┘
                                │
                      cache miss│
                                ▼
                   ┌───────────────────────────┐
                   │      Pinned Staging       │
                   └────────────┬──────────────┘
                                │
                         async H2D
                                ▼
          ┌─────────────────────────────────────────┐
          │              GPU VRAM 16GB              │
          │                                         │
          │  Non-expert weights                     │
          │  Attention / Router                     │
          │  KV Cache                               │
          │  Scratch / CUDA workspace               │
          │                                         │
          │  ┌───────────────────────────────────┐  │
          │  │       Hot Expert Cache            │  │
          │  │       ~6~8 GiB target             │  │
          │  └───────────────────────────────────┘  │
          └────────────────────┬────────────────────┘
                               │
                               ▼
                      GPU MoE Compute
                               │
                               ▼
                        Token Generation
```

---

# 43. 최종 요약

본 프로젝트는 처음에는:

```text
RAM 전체 weight
→ VRAM layer streaming
```

을 목표로 시작하였다.

그러나 실제 실험을 통해:

```text
Dense decode
→ PCIe bottleneck
```

을 확인하였다.

이후:

```text
MoE expert selective streaming
```

으로 연구 방향을 전환하였다.

gpt-oss-120b에서 expert routing locality를 직접 측정하고, expert bundle size와 VRAM budget을 기반으로 cache viability를 검증하였다.

최종적으로:

```text
CPU-MoE
+
Hybrid VRAM Expert Cache
+
llama-server
```

조합에서:

```text
RTX 5060 Ti 16GB
RAM 64GB
gpt-oss-120b
≈ 19.5 ~ 19.9 tok/s
```

수준의 실제 대화형 inference를 확인하였다.

따라서 본 연구의 가장 중요한 결과는 다음과 같다.

> 120B급 MoE 모델을 제한된 VRAM 환경에서 효율적으로 실행하기 위해서는 전체 layer offload보다 **expert 단위 dynamic residency와 PCIe-aware cache 정책**이 더 중요한 최적화 축이다.
