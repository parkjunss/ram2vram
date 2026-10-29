# 구현 및 검증 명세

## 경계

`Tauri → Strata host/UI → Harness → local inference API → Qwen3.8 engine → RAM expert / VRAM cache`

도구 실행은 Harness가 담당하며 모델은 도구 요청을 생성한다. 웹 검색 결과는 다시 로컬 추론 입력으로 돌아온다. 추론이 로컬이어도 웹 검색은 네트워크를 사용한다.

## 구현 순서

- [x] Strata 소스와 MIT 라이선스 확인, 고정 commit 확보.
- [x] 기존 엔진별 Qwen3.8 및 cache 지원 차이 확인.
- [x] 별도 앱 식별자, 데이터 위치, 업데이트 정책을 구성한다.
- [x] 모델 메모리 계획 확인 후 원본 IQ2_XS 양자화와 CUDA 엔진을 준비한다.
- [x] UI와 Windows 데스크톱 실행 파일을 빌드한다.
- [x] 실제 Qwen3.8 대화와 cache 경로를 확인한다. `--pcie-frac 1`을 실제 instance config에서 확인했다.
- [x] 합성 파일 읽기/쓰기, 쓰기 승인/거부, PowerShell 출력, 검색 결과 전달을 검증한다.
- [x] 자체 테스트의 호스트 시작/종료와 kill-on-close Job Object, 준비 모델 중지 후 앱에서 재로딩을 확인한다. 사용 중인 메인 창의 강제 종료/크래시 테스트는 하지 않았다.

## 모델 선택 조건

공식 모델은 125B 본체(토큰당 6B 활성), 별도 n-gram embedding을 가진다. Strata의 원본 ISTA-DASLab pack 중 RAM 여유가 있는 것을 선택하고 Coder/Swift 등 다른 변형으로 자동 대체하지 않는다. n-gram table의 mmap/SSD 경로와 expert의 RAM 경로를 구분해 기록한다. GGUF 파일 크기를 VRAM 요구량으로 해석하지 않는다.

## 재현과 증거

소스 commit, 설정, 빌드 명령, 모델 pack 이름, 실제 GPU, 테스트 결과를 기록한다. 합성 입력만 버전 관리하며 대화·키·모델·빌드·개인 설정은 제외한다. upstream 소스 변경은 패치로 보존하고 재적용 가능하게 한다.

실행 방법은 `desktop/README.md`, 이번 실측 결과는 `docs/desktop/Validation.md`를 참조한다.

## 참고

- https://huggingface.co/Qwen/Qwen3.8-Flash-Next
- https://github.com/Niko1221/Strata
- `desktop/strata/docs/MODELS.md`
- `desktop/strata/apps/host/server/agent/README.md`
