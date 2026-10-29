# RAM2VRAM Desktop

2026-10-29 확정 방향: Strata 기반 데스크톱 앱을 먼저 완성하고, 대화·작업 중심 자체 UI도 별도 실행 파일로 제공한다. 자체 UI 구현과 검증은 [Workspace.md](Workspace.md)에 기록한다.

## 목적

Qwen3.8-Flash-Next의 expert를 시스템 RAM에 두고 필요한 expert를 GPU VRAM에 캐시하면서, 로컬 모델이 파일 도구와 웹 검색을 사용하는 데스크톱 작업 환경을 제공한다.

## 구성과 출처

- Strata 0.2.7 소스: `desktop/strata`, upstream `https://github.com/Niko1221/Strata`, commit `46c152a1310f77cd2f0ce2c7cd213962df14fe83`.
- Strata의 Tauri 창, React UI, Node host, Harness 도구 실행 계층을 재사용한다. MIT 저작권 고지를 유지한다.
- 최초 Qwen3.8 실행 기준선은 Strata의 RAM expert / VRAM cache 엔진이다. 이 코드는 Strata 구현이며, 기존 RAM2VRAM llama.cpp cache를 이식한 것으로 표현하지 않는다.
- Strata 기본값은 일부 미스를 CPU에서 계산한다. RAM2VRAM 구성은 `--pcie-frac 1`로 미스 expert의 GPU 전송을 요청한다. GPU 캐시는 `auto`로 남은 VRAM을 사용한다.
- 기존 llama.cpp-hybrid-cache는 Qwen3.8 아키텍처가 확인되지 않았다. 별도 llama.cpp에는 qwen4exp가 있지만 기존 캐시 옵션이 없고 사용자의 CUDA 변경이 있다. 해당 체크아웃은 변경하지 않는다.
- 기존 Strata 설치와 대화 데이터는 재사용하거나 이전하지 않는다. 앱별 상태를 분리한다.

## 완료 기준

독립 데스크톱 창에서 실제 Qwen3.8 응답, 파일 읽기, 승인 후 파일 쓰기와 명령 실행, 웹 검색 결과와 출처 확인, 중지와 재실행이 동작해야 한다. 모델 로딩, GPU cache 동작, 앱 빌드, 도구 검증은 각각 증거를 남긴다. UI만 실행한 상태를 모델 교체 완료로 보지 않는다.

## 후속 연구

동일한 양자화와 입력에서 Strata 기준선과 RAM2VRAM 캐시 정책을 비교한다. 캐시 hit, 실제 전송량, prefill/decode, 출력 정확성을 별도 측정하며 다른 모델의 과거 수치를 가져오지 않는다.
