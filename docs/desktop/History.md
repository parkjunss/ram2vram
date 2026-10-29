# 채팅 기록 저장과 복구

현재 Workspace 대화 목록은 WebView2의 localStorage 키 `ram2vram.workspace.v1`에 저장한다. 서버 파일에 자동으로 이중 저장하는 구조는 아니다. Windows 기본 프로필 경로는 `%LOCALAPPDATA%/local.ram2vram.workspace/EBWebView/Default/Local Storage/leveldb`다. LevelDB 파일을 직접 편집하지 않는다.

`RAM2VRAM.exe`와 `RAM2VRAM-Workspace.exe`는 서로 다른 WebView 프로필을 사용한다. localStorage는 접속 주소와 포트에도 종속된다. 다만 2026-10-29 기록 누락 신고에서는 같은 프로필·주소가 확인됐으며, 초기화의 정확한 원인은 아직 확정하지 못했다.

원본 저장소를 변경하지 않고 프로젝트의 `.ram2vram-desktop/recovery/`에 복사했다. 저널의 마지막 정상 JSON에서 메시지 14개와 6개가 있는 두 대화를 추출했다. 백업에는 개인 대화가 포함되므로 Git에 넣거나 공개 배포하지 않는다.

왼쪽 **기록 가져오기**로 복구 폴더의 `latest-chats.json`을 선택한다. 현재 기록을 삭제하지 않고 ID별로 합치며 같은 ID의 더 긴 현재 기록은 보존한다. 읽기·검증·저장이 성공해야 화면을 바꾼다. **기록 내보내기**는 현재 대화를 JSON 파일로 저장한다. 화면에 버튼이 없으면 F5로 새로고침한다.

기록 병합 테스트와 합성 UI의 가져오기·새로고침 유지 검증을 추가했다. 실제 사용자 창의 가져오기는 파일 선택 과정에서 사용자 입력이 감지되어 중단했으며 자동 복원 완료로 기록하지 않는다.
