# RAM2VRAM Workspace — 2026-10-29

대화·작업 중심으로 직접 만든 UI다. `desktop/dist/RAM2VRAM-Workspace.exe` 또는 `scripts/windows/start_ram2vram_workspace.bat`으로 실행한다. 기존 Strata 기반 `RAM2VRAM.exe`도 유지한다.

## 사용

채팅 저장 위치와 기록 가져오기·내보내기는 [History.md](History.md)를 참고한다.

컨텍스트 한도, 자동/수동 압축, 기본 스킬과 스킬 관리의 사용법 및 검증 범위는 [Context-Skills.md](Context-Skills.md)에 기록했다. 자동 승인·계획·자동 에이전트 사용법은 [Modes.md](Modes.md), Windows 화면 조작은 [Screen-Control.md](Screen-Control.md)를 참고한다.

### 응답 설정과 긴 대화 수정 (2026-10-29)

오른쪽 **모델 응답 설정**에서 한국어 우선, Temperature, Top P, Top K, 최대 출력 토큰과 Logit Bias JSON을 저장한다. 한국어 지침은 코드·경로·고유명사를 유지하고 사용자가 다른 언어를 명시하면 그 요청을 따른다. 언어 혼합을 완전히 차단하는 기능은 아니다.

설정은 서버에 저장되며 해당 서버의 로컬 에이전트 대화에 공통 적용된다. 도구를 사용하지 않는 별도 plain API와 클라우드 경로에는 적용하지 않는다. 진행 중인 응답을 끝내고 저장한다. Logit Bias는 모델 tokenizer의 토큰 ID를 키로, -100~100 값을 사용한다. 기본값 `{}`는 비활성이다. 엔진이 지원하지 않으면 요청 오류가 표시되므로 `{}`로 복원한다.

대화 영역에 최소 높이 0과 제한된 grid 행 높이를 적용해 긴 기록이 창을 늘리지 않고 내부에서 스크롤된다. 기존 기록은 유지한다. 80개 문단을 넣은 실제 Edge 휠 스크롤과 입력창 가시성, 설정 저장, 승인·중지 회귀 검증을 통과했다. 생성 설정 검증과 요청 본문 전달 테스트 2개, 기존 스트림 테스트 2개 통과. 기존 프록시 회귀는 5개 통과, 별도 Harness 조건 1개 건너뜀.

실제 Qwen3.8 IQ2_XS에서도 설정 저장 후 파일 읽기·정확한 문자열 반환·대화 복구를 통과했다. `check_logit_bias.py`로 `{"0":0.01}`을 포함한 합성 요청이 수용되고 “안녕하세요”가 반환됨을 확인했다. 이는 Bias 요청 지원 확인이며 특정 언어 차단 효과의 증명은 아니다. 시험 후 Bias는 `{}`로 복원했다. 한국어 우선은 활성화했다.

- 왼쪽: 새 작업과 대화 기록. Ctrl+N으로 새 작업을 시작한다.
- 가운데: 스트리밍 대화, 도구 결과, 승인·거부와 중지. Enter는 전송, Shift+Enter는 줄바꿈이다.
- 오른쪽: 작업 폴더 변경, 설치 모델 선택·로드, 실제 RAM/VRAM 사용량, expert 캐시, 최근 생성 속도와 도구 활동.
- 승인 후 실행, 읽기 전용 계획, 자동 승인, 자동 에이전트 모드를 제공한다. 추가 설정은 왼쪽 아래 Strata 화면 링크로 연다.

기록은 전용 UI의 localStorage에 저장하며 기존 Strata 대화를 가져오지 않는다. 작업 폴더는 도구의 기준 위치이며 접근을 제한하는 보안 샌드박스는 아니다.

## 구성과 종료 동작

`자체 HTML/CSS/JS → Strata Node host / Harness → Qwen3.8 엔진`

전용 Tauri 식별자는 `local.ram2vram.workspace`다. 기존 RAM2VRAM 서버가 있으면 상태와 전용 manifest를 확인하고 연결한다. 이 경우 전용 창을 닫아도 공유 서버를 종료하지 않는다. 서버가 없으면 직접 시작하고 창 종료 시 자신이 시작한 서버와 모델을 정리한다.

기존 앱의 서버를 공유하는 동안 기존 앱을 종료하면 전용 UI의 연결도 끊긴다. 전용 앱을 다시 열어 서버를 시작하고 모델을 로드해야 한다. 서버 소유권을 자동 인계하지 않는다.

엔진은 Strata의 RAM expert / VRAM cache 구현이며 기존 RAM2VRAM llama.cpp 캐시의 포팅이 아니다. IQ2_XS, 32K context, 단일 슬롯, vision off, MTP on과 `--pcie-frac 1` 구성을 사용한다. n-gram embedding은 파일 매핑/OS 캐시를 사용하므로 모델 전체 RAM 상주라고 표현하지 않는다.

## 검증 결과

- Windows release 빌드 및 별도 네이티브 창 실행 확인.
- 합성 UI 통합 검증: 스트리밍, 승인 session/tool ID, 폴더 변경, 대화 저장·복구, 중지, 900px 배치와 모델 HTML 비실행 표시 통과.
- 스트림 파서 테스트 2개 통과: 분할 UTF-8/마지막 개행 없는 프레임, 잘못된 프레임 오류 처리.
- 실제 전용 UI: 모델 로드, Qwen 파일 도구 실행, 임의 문자열 정확한 반환과 대화 복구 통과. 실제 RAM/VRAM 및 9.1GiB 캐시 표시 확인.
- 실제 웹 검색·승인/거부·쓰기·명령의 공통 백엔드 검증은 `Validation.md` 참고. 전용 UI의 승인·중지는 합성 서버로 검증했다.
- 공유 서버 연결/종료 분기는 코드 검토와 빌드로 확인했다. 두 네이티브 앱을 함께 사용하는 종료 검증은 수행하지 않았다.

스크린샷은 `.ram2vram-desktop/logs/workspace-ui/`에 보관하며 Git에서 제외한다. 화면 생성 속도는 해당 요청의 값이며 벤치마크가 아니다.

## 빌드와 재검증

먼저 `desktop/README.md`의 소스 준비와 portable 패키지를 만든다. 저장소 루트에서:

```powershell
python -X utf8 scripts/python/desktop/stage_workspace.py
npm.cmd --prefix desktop/strata/apps/desktop run tauri -- build --no-bundle --config ../../../workspace.tauri.json
python -X utf8 scripts/python/desktop/stage_workspace.py --binary
node --test desktop/workspace-ui/test-core.mjs
node desktop/workspace-ui/verify-ui.mjs
# 실행 중인 서버에서 실제 모델을 로드하고 합성 파일을 읽는다.
node desktop/workspace-ui/verify-live.mjs
```

다른 위치에서는 config 경로를 바꾼다. UI 검증에는 Edge와 host의 playwright-core가 필요하다. 서명된 설치 프로그램이 아닌 로컬 portable 빌드다.
