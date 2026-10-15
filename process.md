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
| 2026-10-15 | test: share one Tk root across app tests | 앱 테스트가 가끔 건너뛰어지던 문제 수정 (Windows에서 Tk를 반복 생성하면 초기화 실패 → 세션당 하나만 생성). 8회 반복 실행 모두 통과 |
| 2026-10-15 | feat: store report records as json | 보고서(.txt) 옆에 처리 결과(.json: 긴급도·보고서·경고·메모 해시) 저장, 대시보드용 불러오기(같은 메모는 최신 1건, 이전 형식/손상 파일 제외)와 긴급도순 정렬. 테스트 52개 통과 |
| 2026-10-15 | feat: add batch processing | 폴더 메모 일괄 처리(최대 4건 동시), 건별 상태(대기/처리 중/완료/건너뜀/실패), 같은 내용 메모 건너뛰기, 한 건 실패해도 나머지 계속. 테스트 59개 통과 |
| 2026-10-15 | feat: CLI batch uses run_batch with priority summary | 터미널 --dir도 일괄 처리 엔진 사용(4건 동시), 진행 [n/전체] 표시와 마지막에 긴급/주의/일반/실패 건수 출력 |
| 2026-10-15 | feat: add batch dashboard to app | 앱에 대시보드 탭 추가: 폴더 전체 처리(4건 동시, 진행률), 요약 타일(전체/긴급/주의/일반/경고/실패), 긴급도순 목록, 선택 시 상세 보고서. 보고서 화면에 긴급도 배지·요약·판단 이유 표시. 테스트 66개 통과 |
| 2026-10-15 | fix: dashboard first, keep buttons visible on narrow windows | 첫 화면을 대시보드로 변경(탭 순서 대시보드 → 메모 작성). 창이 좁으면 '전체 처리'·'복사' 버튼이 잘리던 문제 수정, 폴더 경로 짧게 표시, 표 열 폭·배너 줄바꿈 조정. 테스트 67개 통과 |
| 2026-10-15 | feat: AI insights across reports, dashboard sync fix | 대시보드에 AI 인사이트 추가(보고서 전체의 공통 패턴·주의할 경향·기록 보완점, 근거 메모 표시, 일괄 처리·보고서 추가 시 자동 재분석). 직접 입력한 메모가 대시보드에서 서로 덮어써져 추가가 반영되지 않던 문제 수정(이름+내용이 같을 때만 합침). 최대화로 시작, 화면 배치 압축. 테스트 79개 통과 |
| 2026-10-15 | test: add 40 sample memos for validation | 검증용 샘플 메모 21~60번 추가(안전 사고·설비 이상·품질 보류·정상 마감, 기존 메모와 반복되는 패턴, 빈 메모·CP949 인코딩·영문 혼용·상충 정보 등 예외 사례). 예상 긴급도와 확인할 점은 docs/검증/샘플메모_예상결과.md |
| 2026-10-15 | feat: add unconfirmed-items chart to dashboard | 대시보드에 '미확인 항목이 많은 메모' 막대 차트 추가(상위 8건, 긴급도 색은 상태 팔레트+글자 라벨, 마우스를 올리면 요약 표시, 클릭 시 상세 보고서). AI 인사이트 옆에 배치. 테스트 81개 통과 |
| 2026-10-15 | feat: problem-type pie chart and tile filters | Claude가 보고서마다 주된 문제 유형(설비 이상·수량 불일치·품질·검사·안전·라벨·식별 등)을 분류, 대시보드에 '문제 유형 비율' 원형 그래프 추가(정상·기록 제외, 색은 유형에 고정). 이전 보고서는 다시 분석 시 한 번에 분류. 상단 긴급/주의/일반/경고 타일과 원형 그래프 조각을 누르면 처리 현황이 해당 항목으로 필터링(다시 누르면 해제). 테스트 90개 통과 |
