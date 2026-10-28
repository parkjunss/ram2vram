# RAM2VRAM

Windows와 NVIDIA GPU에서 VRAM보다 큰 MoE 모델을 실행하기 위한 RAM–VRAM 캐시 실험입니다. 현재 공개 범위는 Qwen3.6-35B-A3B 실행 스크립트, llama.cpp MoE cache 엔진 설치 스크립트, 대표 CUDA 전송 벤치마크입니다.

RAM을 실제 VRAM으로 바꾸는 도구는 아닙니다. 모델의 MoE expert를 CPU RAM에 두고 일부를 GPU에 캐시하므로 성능은 GPU, PCIe 대역폭, 모델과 프롬프트에 따라 달라집니다.

## 요구 사항

- Windows x64, Python 3.11+, Git
- Visual Studio 2022 C++ Build Tools, CMake 3.24+, Ninja
- NVIDIA 드라이버와 CUDA Toolkit
- Qwen GGUF 약 22.1GB, 다운로드 조립 중 약 44.3GB의 여유 저장 공간

## 설치 및 실행

**x64 Native Tools Command Prompt for VS 2022**에서 저장소 루트로 이동해 실행합니다.

```bat
scripts\windows\setup_hybrid_moe_cache.bat
scripts\windows\setup_qwen36.bat
scripts\windows\chat_qwen36_cli.bat
```

설치 스크립트는 MoE cache 포크의 고정 커밋을 별도 폴더에 내려받아 빌드합니다. GPU 아키텍처 기본값은 `native`입니다. 필요한 경우 빌드 전에 `set RAM2VRAM_CUDA_ARCH=120`처럼 지정합니다.

OpenAI 호환 로컬 서버:

```bat
scripts\windows\chat_qwen36_server.bat --port 8081
python scripts\python\test_qwen36_server.py 8081
```

기본 모델 ID는 `qwen3.6-35b-a3b`, 컨텍스트는 4,096, reasoning은 off입니다. CLI와 서버를 동시에 실행하면 모델과 GPU 메모리가 중복 사용되므로 하나씩 실행합니다.

캐시 OFF/8GiB A/B 실행:

```bat
scripts\windows\run_qwen36_cache_ab.bat
```

## 선택 기능: Strata

[Strata](https://github.com/Niko1221/Strata)를 별도로 설치한 경우 로컬 Qwen 서버와 도구 UI를 연결할 수 있습니다.

```bat
set RAM2VRAM_STRATA_INSTALL=C:\tools\Strata
scripts\windows\start_strata_qwen36.bat
```

Strata 상태와 대화 기록은 `.strata-ram2vram/`에 저장되며 Git에 포함되지 않습니다. 파일·셸 도구는 로컬 PC에 접근하므로 처음에는 Manual 모드를 권장합니다.

## 대표 CUDA 벤치마크

```bat
cmake -S benchmark -B benchmark\build
cmake --build benchmark\build --config Release
```

공개 저장소에는 `benchmark/ram_to_vram_bench.cu`와 빌드 설정만 포함합니다. 나머지 과거 실험, 측정 로그, 모델, 엔진 빌드, 개인 파일 정리 도구와 문서는 로컬에만 보존합니다.

## 외부 프로젝트와 모델

- [llama.cpp](https://github.com/ggml-org/llama.cpp) 및 [MoE cache 포크](https://github.com/leloch/llama.cpp): 별도 다운로드
- [Qwen3.6-35B-A3B](https://huggingface.co/Qwen/Qwen3.6-35B-A3B)
- [Qwen GGUF](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF), revision `a483e9e6cbd595906af30beda3187c2663a1118c`
- 모델 SHA256: `ac0e2c1189e055faa36eff361580e79c5bd6f8e76bffb4ce547f167d53e31a61`

각 외부 프로젝트와 모델의 라이선스를 따릅니다. 이 저장소 자체의 라이선스는 아직 지정하지 않았습니다.

## 검증 범위

스크립트 경로와 Python 문법은 로컬에서 확인합니다. 전체 CUDA 재빌드, 신규 모델 다운로드, 다른 GPU에서의 성능과 Strata 64K 컨텍스트는 별도 검증 대상입니다.
