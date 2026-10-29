# 검증 기록 — 2026-10-28

## 실제 결과

- Windows portable 실행 파일: `desktop/dist/RAM2VRAM.exe`.
- Strata 기반의 실제 Tauri 창을 확인했다. 창 제목은 `RAM2VRAM — powered by Strata`이며 기존 UI와 도구 화면을 재사용한다.
- 원본 Qwen3.8-Flash-Next GSQ-RCO IQ2_XS, CUDA 엔진 0.1.52, 컨텍스트 32,768, 슬롯 1, 이미지 끔, MTP 사용.
- 장비: RTX 5060 Ti 16,311 MiB, 물리 RAM 68,639,150,080 bytes.
- 실제 앱 서버 로그: expert 33.02 GiB RAM 적재, GPU cache 6,789 experts / 9.10 GiB. 첫 앱 로딩 약 33초 시점에 expert 적재 완료 기록.
- 실제 instance 설정: `--expert-cache auto`, `--max-context 32768`, `--pcie-frac 1`.
- n-gram 테이블 약 28.8GB는 파일 매핑/OS cache 경로다. 모델 전체 RAM 상주라고 표현하지 않는다.
- 첫 파일 읽기 턴의 짧은 측정: 도구 호출 생성 31.5 tok/s, 후속 답변 37.9 tok/s. 장시간 성능 벤치마크나 기존 모델과의 비교 결과가 아니다.

## 빌드와 테스트

| 검사 | 결과 | 범위 |
| --- | --- | --- |
| UI production build | 통과 | Vite, 큰 chunk 경고 존재 |
| TypeScript typecheck | 통과 | UI 정적 타입 |
| Tauri Windows release build | 통과 | `--no-bundle`, 로컬 portable 구성 |
| packaged self-test | 13 항목 통과 | 호스트/리소스/Node/Control/Job Object/종료 |
| host API·도구·검색 회귀 | 53 통과, 15 skip | 합성 provider, 승인 정책, 검색 파싱·장애 처리. skip은 실제 브라우저 등 별도 조건 |
| host 상태 경로 | 8 통과 | 기존 7개 + RAM2VRAM override 1개 |
| Python 상태 격리 | 3 통과 | 환경 덮어쓰기 및 upstream 실제 경로 해석 |
| 실제 모델 파일 읽기 | 통과 | 무작위 nonce를 파일 도구로 읽고 정확히 답변 |
| 실제 모델 웹 검색 | 통과 | Manual 승인 → 실제 검색 → Python 공식 문서 URL 답변 |
| 실제 모델 파일 쓰기 | 통과 | 지정 합성 경로만 승인, 정확한 내용 저장 |
| 실제 모델 쓰기 거부 | 통과 | 승인 거부 후 파일 미생성 확인 |
| 실제 모델 PowerShell | 통과 | `Write-Output`으로 nonce 출력, 모델이 정확한 결과 반환 |

네트워크·ACL 검사에 필요한 Windows 권한으로 테스트를 실행했다. 테스트 임시 폴더는 프로젝트 내부로 지정하고 Windows PowerShell 모듈 경로를 명시했다. 실제 브라우저 MCP 조작, 사용자 API 키 제공자, 장기 안정성, GPU OOM 복구, 설치 프로그램/코드 서명은 검증하지 않았다.

## 상태와 출처

원본 테스트 프레임과 로그는 `.ram2vram-desktop/logs/`, 실제 엔진 로그는 `.ram2vram-desktop/runtime/app-1.server.log`에 있다. 민감한 설정과 원본 대화는 Git에 포함하지 않는다. 초기 준비 작업이 기본 Strata launch 폴더에 만든 세 파일은 이 작업이 만든 파일임을 확인하고 `.ram2vram-desktop/launch/`로 옮겼다. 이후 경로는 Python과 Node 모두 전용 상태 폴더로 통일했다.

현재 캐시 구현의 출처는 Strata다. 기존 RAM2VRAM llama.cpp cache 이식 및 캐시 정책 성능 개선은 이번 완료 범위에 포함되지 않는다. 앱 설정은 미스 expert를 GPU로 전송하도록 명시했으며, 엔진의 cache hit 표시와 PCIe 전송 비율을 함께 읽어야 한다.
