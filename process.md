# 작업 이력 (process.md)

커밋할 때마다 아래에 한 줄씩 추가합니다. 최신 항목이 맨 아래입니다.
(커밋 해시는 커밋 후에 정해지므로, 각 항목은 커밋 메시지로 찾을 수 있습니다: `git log --oneline`)

| 일시 | 커밋 | 내용 |
|---|---|---|
| 2026-10-15 08:16 | `b2bd661` chore: initial import | 실습 자료(실습_1.docx, 참고 메모 20개), 설계 문서·구현 계획 등록. API 키 파일은 git 제외 |
| 2026-10-15 08:18 | `3084b5d` feat: add report schema | 보고서 구조(발생한 일/조치/현재 상태/확인 사항/미확인) 정의, 항목마다 원문 근거 문장 포함 |
| 2026-10-15 08:18 | `ece698d` feat: add hallucination checks | 원문에 없는 숫자·근거 문장·단정 표현 자동 점검 |
| 2026-10-15 08:18 | `837236e` feat: add report renderer | 고정 양식 텍스트 보고서 출력 (빈 항목 "메모에 기록 없음", "○○: 미확인") |
| 2026-10-15 08:19 | `3ad821f` feat: add Claude summarize call | Claude API(claude-opus-5-5) 호출, 지시문 작성, 거절·잘림 처리 |
| 2026-10-15 08:20 | `ff5ff04` feat: add CLI | 터미널 실행(붙여넣기/--file/--dir), 저장, API 키를 claudeapi.txt에서 읽기 |
| 2026-10-15 08:23 | `61e2c62` docs: add README | 설치·실행 방법. 실제 API로 메모 20개 실행: 20개 모두 생성, 점검 항목 통과 |
| 2026-10-15 | fix: address final review findings | 최종 검토 반영: ① 응답 형식 오류가 전체 실행을 멈추던 문제 → 해당 메모만 실패 처리 ② CP949(한글 메모장) 메모도 읽기, 못 읽는 파일은 건너뛰기 ③ 자동 점검 오탐 수정("해결 여부는 확정 아님" 같은 유보 표현은 경고 안 함, "문제 없음" 띄어쓰기 변형도 잡음). 테스트 27개 통과 |
| 2026-10-15 | refactor: add shared generate service | 메모→보고서→점검→저장 흐름을 handover/service.py로 묶음 (CLI와 tkinter 앱이 함께 사용). GitHub 저장소(boyoung83/A2A_Example) 연결. 테스트 30개 통과 |
| 2026-10-15 | feat: load API key from .env | API 키를 .env(ANTHROPIC_API_KEY=...)에서 읽도록 변경, .env.example 추가, .env는 git 제외. claudeapi.txt는 더 이상 사용 안 함 |
| 2026-10-15 | feat: add tkinter desktop app | 데스크톱 앱(app.py): 메모 입력·파일/예시 불러오기, 항목별 색상 카드로 보고서 표시, 자동 점검 배너, 복사·파일 열기, 최근 보고서 목록. API 호출은 백그라운드로 실행(화면 멈춤 없음). 실제 API로 메모 01 생성 확인. 테스트 34개 통과 |
| 2026-10-15 | feat: add priority and detailed sections to report | 보고서 상세화: 한 줄 요약·시간순 경과·주요 수치/대상·연락/요청 현황 추가, Claude가 긴급도(긴급/주의/일반)와 판단 이유를 함께 판단. 새 항목도 원문 대조 점검. 테스트 45개 통과 |
