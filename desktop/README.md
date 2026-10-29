# RAM2VRAM Desktop (Strata 기반)

소스 기준: Strata `46c152a1310f77cd2f0ce2c7cd213962df14fe83` (0.2.7, MIT).
개발 원본은 `desktop/strata`, 재적용 가능한 변경은 `desktop/ram2vram.patch`에 있다.
기존 llama.cpp 체크아웃과 설치된 Strata의 설정·대화는 변경하지 않는다.

## 실행

빌드가 준비되면 `desktop/dist/RAM2VRAM.exe`를 실행한다. `scripts/windows/start_ram2vram_desktop.bat`도 같은 앱과 상태를 사용한다.
`desktop/dist/ram2vram.json`은 작업 폴더 위치만 가진다. 이 폴더를 다른 PC로 옮길 때는 `workspaceRoot`를 수정하고 모델과 런타임을 준비해야 한다.

- 상태·키·대화·엔진: `.ram2vram-desktop/`
- 모델: `models/qwen38/`
- 기본 앱 주소: `http://127.0.0.1:47832`
- 기본 모델: 원본 Qwen3.8-Flash-Next, ISTA-DASLab IQ2_XS, 32K 컨텍스트, 단일 슬롯, 이미지 끔
- 캐시: `--expert-cache auto`, `--pcie-frac 1` (미스 expert GPU 전송). Strata의 기본 CPU/GPU 혼합 미스 처리를 그대로 쓰는 설정이 아니다.

최초 모델 준비는 아래 명령으로 진행한다. 다운로드와 모델 변환은 재개 가능하다.

```powershell
python -X utf8 scripts/python/desktop/prepare_model.py --plan
python -X utf8 scripts/python/desktop/prepare_model.py
```

준비용 CLI가 서버를 시작한 상태에서는 앱에서 두 번째로 같은 모델을 로딩하지 않는다. 준비 서버를 해당 프로필로 종료한 후 앱의 Models에서 IQ2_XS를 로드한다. 앱이 실행 중일 때 `configure_app.py`로 같은 로딩을 요청할 수도 있다.

```powershell
python -X utf8 scripts/python/desktop/prepare_model.py --stop
python -X utf8 scripts/python/desktop/configure_app.py
```

## 소스 재현

새 작업 폴더에서 소스를 가져와 고정 commit에 패치를 적용한다.

```powershell
git clone https://github.com/Niko1221/Strata.git desktop/strata
git -C desktop/strata checkout --detach 46c152a1310f77cd2f0ce2c7cd213962df14fe83
git -C desktop/strata apply ../ram2vram.patch
npm.cmd --prefix desktop/strata/apps/host ci --no-audit --no-fund
npm.cmd --prefix desktop/strata/apps/desktop ci --no-audit --no-fund
python -X utf8 desktop/strata/apps/desktop/scripts/stage-control.py
```

Node와 Harness는 Strata의 공식 staging 절차를 따른다. 이번 로컬 빌드는 설치된 `F:/Strata/node`와 `F:/Strata/harness`의 **배포용 런타임만** `apps/desktop/src-tauri/resources/` 아래에 복사했다. Node v24.12.0, Harness 0.2.1-alpha.3이며 개인 데이터는 이 경로에 포함하지 않는다. 새 환경에서는 `fetch-node.ps1`과 `stage-harness.mjs`를 사용한다. Control은 고정 interpreter/wheel 검증을 수행하는 `stage-control.py`로 새로 생성했다.

UI 빌드 후 `apps/desktop`에서 다음을 실행한다. Rust/MSVC와 WebView2가 필요하다.

```powershell
npm.cmd --prefix desktop/strata/apps/host run build
npm.cmd --prefix desktop/strata/apps/host run typecheck
# cwd: desktop/strata/apps/desktop
npm.cmd run tauri -- build --no-bundle
# cwd: repository root
python -X utf8 scripts/python/desktop/package_portable.py
```

이 결과는 로컬 portable 폴더이며 설치 프로그램이나 서명된 배포본이 아니다. 앱 업데이트는 upstream 설치 프로그램으로 이 커스텀 빌드를 덮어쓰지 않도록 차단했다. 엔진 업데이트는 Strata Control의 서명 검증을 유지한다.

## 검증

```powershell
python -X utf8 scripts/python/desktop/test_runtime.py
python -X utf8 scripts/python/desktop/check_host.py
# 앱과 실제 Qwen3.8이 준비된 이후
python -X utf8 scripts/python/desktop/smoke.py
python -X utf8 scripts/python/desktop/smoke.py --web
python -X utf8 scripts/python/desktop/smoke.py --deny-write
python -X utf8 scripts/python/desktop/smoke.py --write
python -X utf8 scripts/python/desktop/smoke.py --command
```

검색 테스트는 공개 Python 문서 질의 한 건만 승인한다. 다른 도구의 승인 요청은 거절한다. 파일 테스트는 임의 문자열을 가진 합성 파일만 읽는다. 원본 결과는 `.ram2vram-desktop/logs/`에 보관하며 Git에는 포함하지 않는다.

## 직접 만든 대화·작업 UI

오른쪽 **컨텍스트 · 스킬**에서 컨텍스트 한도 조절·모델 재로드, 자동 압축 상태 확인·즉시 압축, 스킬 추가·편집·활성화·삭제와 `SKILL.md` 가져오기/내보내기를 지원한다. [사용법과 검증](../docs/desktop/Context-Skills.md)을 참고한다.

`desktop/dist/RAM2VRAM-Workspace.exe` 또는 `scripts/windows/start_ram2vram_workspace.bat`으로 실행한다. 기존 Strata 기반 실행 파일도 유지한다. 자체 대화 기록, 작업 폴더, 스트리밍, 도구 승인·중지와 RAM/VRAM 상태를 제공한다. 빌드·검증·공유 서버 종료 동작은 [Workspace 안내](../docs/desktop/Workspace.md)에 기록했다.

## 엔진 출처

현재 Qwen3.8 기준선은 **Strata의 RAM expert / VRAM expert cache 구현**이다. 기존 RAM2VRAM llama.cpp cache 포팅이나 성능 개선이 완료됐다는 뜻은 아니다. n-gram embedding의 파일 매핑과 expert의 RAM 상주를 구분한다. 개선 수치는 같은 모델·입력·메모리 예산에서 별도로 검증한다.
