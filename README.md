# RAM2VRAM

16GB VRAM에서 120B급 MoE 모델의 로컬 추론을 개선하기 위해 RAM↔VRAM 전송, expert routing locality, VRAM-resident expert cache를 실험한 연구 프로젝트입니다.

핵심 결과는 두 가지입니다. Dense weight streaming은 약 14.1–14.3 GB/s의 PCIe H2D 대역폭에 막혔고, MoE routing trace에는 반복성이 있어 8GiB global cache 시뮬레이션에서 78.81% hit rate를 보였습니다. 실제 hybrid cache 실험은 gpt-oss-120b의 generation을 약 6.6 tok/s에서 7.5 tok/s로 개선했습니다.

- [전체 연구 보고서](docs/research-report.md)
- [연구 코드와 재현 방법](research/README.md)
- [36-layer trace](research/data/traces/moe_expert_trace_all.csv) · [127-step partial trace](research/data/traces/moe_expert_trace.csv)
- [실행별 요약 CSV](research/results/benchmark-summary.csv)

## 핵심 결과

| 항목 | 결과 |
| --- | ---: |
| PCIe H2D 실효 대역폭 | 14.1–14.3 GB/s |
| gpt-oss expert bundle | 12.607 MiB |
| 전체 expert tensor | 56.731 GiB |
| 36-layer, 55-step trace의 global 8GiB cache | 78.81% hit |
| 위 조건의 추정 전송량 | 384.62 MiB/token |
| 29-layer, 127-step trace의 per-layer cache32 | 87.71% hit |

아래 성능은 동일 프롬프트의 짧은 단일 실행 결과입니다. `cache off`는 같은 실험 엔진에서 캐시를 끈 기준선이며, 별도 stock 바이너리 측정으로 표기하지 않습니다.

| 모델 / 구현 | Cache off | Cache on | 변화 | Cache hit |
| --- | ---: | ---: | ---: | ---: |
| gpt-oss-120b hybrid, 8GiB | 6.6 tok/s | 7.5 tok/s | +13.6% | 미계측 |
| Qwen3.5-35B-A3B, 8GiB | 27.27 tok/s | 28.72 tok/s | +5.3% | 74.9% |
| Qwen3.6-35B-A3B, 8GiB | 26.63 tok/s | 27.49 tok/s | +3.2% | 71.9% |

Persistent slot-remap 방식은 8.2 tok/s 기준선보다 느린 3.1–3.3 tok/s를 기록했습니다. 높은 hit rate만으로는 성능이 보장되지 않으며 slot remap, synchronization, dispatch overhead가 전체 이득을 상쇄할 수 있다는 실패 사례입니다.

## 저장소 구조

| 경로 | 내용 |
| --- | --- |
| `docs/` | 연구 보고서와 과정 기록 |
| `research/global-cache/` | expert 크기 추출 및 global LRU 시뮬레이션 |
| `research/optimizer/` | VRAM budget별 cache 배치 비교 |
| `research/probes/` | llama.cpp MoE routing 계측 도구 |
| `research/data/traces/` | 재분석 가능한 원본 routing trace |
| `research/results/` | 원본 로그에서 추린 실행별 요약 |
| `benchmark/` | 대표 CUDA RAM→VRAM 전송 벤치마크 |
| `scripts/` | 현재 Qwen 모델 설치·실행·검증 도구 |

## 분석 재현

Python 3.11 이상만 필요합니다.

```bat
python research\probes\stage2\analyze_moe_trace.py research\data\traces\moe_expert_trace_all.csv
python research\global-cache\simulate_global_expert_cache.py research\data\traces\moe_expert_trace_all.csv research\data\gpt_oss_expert_sizes.json
python research\optimizer\optimize_vram_allocation.py research\data\traces\moe_expert_trace_all.csv research\data\gpt_oss_expert_sizes.json --budgets-gib 4,8,12
```

CUDA 벤치마크와 현재 Qwen 실행 방법은 [연구 보고서](docs/research-report.md)와 `scripts/windows/`를 참고하세요. 모델과 llama.cpp 체크아웃은 저장소에 포함하지 않으며 설치 스크립트가 고정 커밋을 사용합니다.

## 데이터 범위와 한계

- 36-layer trace는 55 decode step, partial trace는 layers 7–35의 127 step입니다.
- cache simulation의 PCIe 시간은 14.2 GB/s를 가정한 transfer-only 추정치입니다. routing, compute, synchronization 비용은 별도입니다.
- tokens/s 결과는 장시간 평균이나 다중 seed 품질 벤치마크가 아닙니다.
- Windows/WDDM 및 단일 16GB RTX 5060-class 환경의 결과라 다른 시스템에서 달라질 수 있습니다.

## 공개하지 않는 항목

모델 파일, `llama.cpp*` 체크아웃, 원본 실행 로그, Strata 대화 기록, 로컬 백업, 개인 파일 정리 결과는 `.gitignore`로 제외합니다. 원본 로그에는 로컬 절대 경로가 포함되어 있어 요약 CSV만 공개합니다.

## License

이 저장소의 자체 코드와 문서는 [MIT License](LICENSE)로 공개합니다. llama.cpp, Strata, Qwen/gpt-oss 모델과 기타 외부 구성요소에는 각각의 라이선스가 적용됩니다.
