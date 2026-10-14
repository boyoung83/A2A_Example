# 일괄 처리 + 긴급도 대시보드 + 상세 보고서 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 보고서에 긴급도·상세 항목을 추가하고, 폴더 일괄 처리와 긴급도순 대시보드를 앱에 넣는다.

**Architecture:** `HandoverReport` 스키마를 확장해 한 번의 API 호출로 긴급도·상세 항목을 받는다. 결과는 `.txt` 옆 `.json`(store)으로 남고, 대시보드는 store를 읽는다. 일괄 처리(batch)는 스레드 풀로 돌리고 진행 상황을 콜백으로 알린다. 앱은 보고서 카드 화면을 `ReportView` 컴포넌트로 분리해 두 탭에서 재사용한다.

**Tech Stack:** Python 3.12, anthropic, pydantic, tkinter/ttk, pytest

**Spec:** `docs/superpowers/specs/2026-10-15-batch-dashboard-design.md` (기존: `docs/superpowers/specs/2026-10-15-handover-report-design.md`)

## Global Constraints

- 긴급도 값은 정확히 `"긴급"`, `"주의"`, `"일반"`; 정렬 순서도 이 순서
- 모든 새 항목은 메모 원문 근거(`source_quote`)를 가진다 (요약·긴급도 이유 제외)
- 동시 처리 최대 4건; 한 건 실패가 전체를 멈추지 않음; 화면이 멈추지 않음
- `.json` 사이드카는 `.txt`와 같은 이름(확장자만 다름), UTF-8
- 커밋마다 `process.md`에 이력 한 줄 추가 (사용자 요청)
- 보고서 표시 순서: 긴급도 → 한 줄 요약 → 발생한 일 → 조치한 내용 → 현재 상태 → 다음 근무자 확인 사항 → 시간순 경과 → 주요 수치·대상 → 연락·요청 현황 → 미확인 사항

## Review Focus

1. 이전 형식(긴급도 없는) `.json`이나 깨진 `.json`이 `reports/`에 있음 → 대시보드가 그 파일만 건너뜀 (Task 2 테스트)
2. 같은 메모 이름이 여러 번 처리됨 → 대시보드엔 최신 하나 (Task 2 테스트)
3. 일괄 처리 중 일부 실패·일부 건너뜀 → 나머지 완료, 요약에 실패 수 반영 (Task 3 테스트)
4. 폴더에 `.txt`가 없음 → 안내 문구, API 호출 없음 (Task 5 테스트)
5. 일괄 처리 중 다시 `전체 처리` 클릭 → 두 번째 실행 무시 (Task 5 테스트)

---

### Task 1: 스키마 확장 + 지시문 + 점검 + 텍스트 렌더링

**Files:** Modify `handover/schema.py`, `handover/prompt.py`, `handover/checks.py`, `handover/render.py`, `handover/view.py`; tests `tests/conftest.py`, `tests/test_schema.py`, `tests/test_checks.py`, `tests/test_render.py`, `tests/test_app.py`

**Interfaces — Produces:**
- `Priority = Literal["긴급", "주의", "일반"]`, `PRIORITY_ORDER = ["긴급", "주의", "일반"]`
- `TimelineEntry(time: str, text: str, source_quote: str)`, `Fact(label: str, value: str, source_quote: str)`, `Contact(party: str, request: str, status: str, source_quote: str)`
- `HandoverReport` 필드 순서(모델이 내용을 먼저 쓰고 판단은 마지막에): `summary, events, actions, current_status, next_checks, timeline, key_facts, contacts, unconfirmed, priority_reason, priority`
- `tests/conftest.py`: `make_report(**kw) -> HandoverReport` (빈 목록·`summary=""`·`priority="일반"`·`priority_reason=""` 기본값)
- `build_sections`는 8개 섹션: 기존 5개 + `시간순 경과`(kind `timeline`, 줄 형식 `"{time}  {text}"`), `주요 수치·대상`(kind `facts`, `"{label}: {value}"`), `연락·요청 현황`(kind `contacts`, `"{party} — {request} — {status}"`); 순서는 Global Constraints

- [ ] **Step 1: 실패 테스트**
  - `test_schema`: 새 필드 포함 roundtrip; `HandoverReport.model_fields`의 키 순서가 위와 같음; `priority="급함"`은 ValidationError
  - `test_checks`: `TimelineEntry(time="10:30", ...)`처럼 원문에 없는 시각 → `'10:30'` 경고; `Fact(value="15개")` 원문에 없음 → `'15'` 경고; `Contact` 근거 문장 가짜 → 근거 경고; `summary="문제 해결됨"` → `'해결'` 경고; `priority_reason`의 원문 없는 숫자 → 경고
  - `test_render`: 헤더에 `" 긴급도: [긴급] {reason}"`, `" 요약: {summary}"`; 섹션 제목 9개(`■ 발생한 일` … `■ 미확인 사항`) 순서; 빈 섹션 `- 메모에 기록 없음` 8개
  - `test_app::test_build_sections_*`: 8개 섹션 제목 순서, 각 kind의 줄 형식
- [ ] **Step 2:** `python -m pytest -q` → 위 테스트 FAIL
- [ ] **Step 3:** 구현. `SYSTEM_PROMPT`에 추가할 규칙(고정 문구):

```
8. summary에는 다음 근무자가 가장 먼저 알아야 할 핵심을 한 문장으로 쓰세요. 메모에 없는 내용은 넣지 마세요.
9. timeline에는 메모에 시각이 적힌 기록만 시간 순서로 넣으세요. time은 원문 표기 그대로 씁니다.
10. key_facts에는 설비·라인·주문·LOT·제품과 수량을 원문 표기 그대로 넣으세요.
11. contacts에는 누구에게 무엇을 전달·요청했는지와 회신 상태를 넣으세요. 상태가 적혀 있지 않으면 "회신 여부 미기록"이라고 쓰세요.
12. priority는 메모 내용만 보고 판단하세요.
   - 긴급: 다음 근무자가 교대 직후 바로 조치해야 함 (안전 위험, 설비 정지·이상이 해결되지 않음, 불량 확산 우려 등)
   - 주의: 근무 중 확인이 필요함 (품질 판정·서류·회신 대기, 출하·납품·수량 영향 등)
   - 일반: 마감되었거나 기록용으로 급한 확인이 없음
   priority_reason에는 메모의 어떤 내용 때문에 그렇게 판단했는지 한 문장으로 쓰세요. 메모에 없는 위험을 지어내지 마세요.
```

- [ ] **Step 4:** `python -m pytest -q` → 전체 PASS (기존 테스트는 `make_report`로 갱신)
- [ ] **Step 5:** `process.md` 한 줄 + commit `"feat: add priority and detailed sections to report"`

### Task 2: 결과 저장소 (store)

**Files:** Create `handover/store.py`, `tests/test_store.py`; Modify `handover/service.py`, `tests/test_service.py`

**Interfaces:**
- Consumes: `HandoverReport`, `PRIORITY_ORDER` (Task 1), `GenerationResult` (기존)
- Produces:
  - `content_hash(memo: str) -> str` — 공백 정규화 후 sha256 hex
  - `@dataclass Record: source_name: str; created_at: datetime; memo_hash: str; memo: str; report: HandoverReport; warnings: list[str]; txt_path: Path`
  - `save_record(record: Record) -> Path` — `record.txt_path.with_suffix(".json")`에 저장
  - `load_records(out_dir: Path) -> list[Record]` — 읽기 실패·검증 실패 파일은 건너뜀; 같은 `source_name`은 `created_at` 최신 하나
  - `sort_for_dashboard(records) -> list[Record]` — 긴급도 순, 같은 등급은 `created_at` 내림차순
  - `GenerationResult`에 `record: Record` 추가; `generate()`가 `.json`도 저장

- [ ] **Step 1: 실패 테스트**: save→load roundtrip; 같은 이름 두 건 → 최신 하나; 이전 형식 json(`{"foo": 1}`)·깨진 json(`"{"`) 무시; 정렬(일반·긴급·주의 → 긴급·주의·일반, 동급은 최신 먼저); `content_hash("a  b\n") == content_hash("a b")`; `generate()` 후 `.json` 존재
- [ ] **Step 2:** FAIL 확인 → **Step 3:** 구현 → **Step 4:** PASS
- [ ] **Step 5:** `process.md` + commit `"feat: store report records as json"`

### Task 3: 일괄 처리 (batch)

**Files:** Create `handover/batch.py`, `tests/test_batch.py`

**Interfaces:**
- Consumes: `generate` (Task 2), `read_memo_file`, `content_hash`, `ReportError`
- Produces:
  - `find_memos(folder: Path) -> list[Path]` — `*.txt` 이름순
  - `@dataclass BatchItem: path: Path; status: str; message: str = ""; record: Record | None = None` — status ∈ `"대기"`, `"처리 중"`, `"완료"`, `"건너뜀"`, `"실패"`
  - `run_batch(paths, client, out_dir, on_update, skip_hashes: set[str] | None = None, workers: int = 4) -> list[BatchItem]` — 항목마다 상태가 바뀔 때 `on_update(item)` 호출(워커 스레드에서 호출될 수 있음); 빈 메모·읽기 실패·`ReportError`·`OSError` → `"실패"` + message; `skip_hashes`에 해시가 있으면 `"건너뜀"`(API 호출 없음)
  - `count_by_priority(records) -> dict[str, int]` — 키 `"긴급","주의","일반"`

- [ ] **Step 1: 실패 테스트**: 3개 파일(정상·빈 파일·거절) workers=1 → 상태 `완료/실패/실패`, 저장 1건; skip_hashes로 1건 건너뜀 + `fake.calls` 감소; workers=4로 5건 모두 완료; on_update가 각 항목에 대해 `"처리 중"` 후 최종 상태 순으로 호출됨; `count_by_priority`
- [ ] **Step 2–4:** FAIL → 구현(`concurrent.futures.ThreadPoolExecutor`) → PASS
- [ ] **Step 5:** `process.md` + commit `"feat: add batch processing"`

### Task 4: CLI 연동

**Files:** Modify `handover_report.py`, `tests/test_cli.py`

`--dir`은 `run_batch`로 처리하고(진행 줄 `[n/total] 이름 — 상태`), 끝에 `긴급 n건 · 주의 n건 · 일반 n건 · 실패 n건` 출력. 텍스트 보고서 출력은 `--file`/붙여넣기에서만. 종료코드 규칙 유지.

- [ ] **Step 1: 실패 테스트**: `--dir` 출력에 `긴급 0건 · 주의 0건 · 일반 1건 · 실패 1건` 포함 (기존 `test_dir_continues_after_failure` 데이터 기준)
- [ ] **Step 2–4:** FAIL → 구현 → 전체 PASS
- [ ] **Step 5:** `process.md` + commit `"feat: CLI batch uses run_batch with priority summary"`

### Task 5: 앱 — 탭, ReportView, 대시보드

**Files:** Modify `app.py`, `tests/test_app.py`

**Interfaces:**
- Consumes: `load_records`, `sort_for_dashboard`, `run_batch`, `find_memos`, `count_by_priority`, `build_sections`
- Produces (테스트용 공개 메서드): `show_tab(name: str)` (`"editor"`/`"dashboard"`), `run_batch()`, `dashboard_rows() -> list[tuple]` (긴급도, 메모 이름, 요약, 이유, 미확인 수, 경고 수), `tile_counts() -> dict[str, int]` (키 `전체, 긴급, 주의, 일반, 경고, 실패`), `select_dashboard_row(index: int)`, `detail_status_text() -> str`

화면:
- 헤더 가운데 세그먼트 탭 `메모 작성 | 대시보드`
- 대시보드: 상단 툴바(폴더 경로, `폴더 변경`, `이미 처리한 메모 건너뛰기` 체크(기본 켬), `전체 처리` 주 버튼, 진행 막대 + `n/total 처리 중 · 실패 n`) → 요약 타일 6개(긴급=빨강 `#DC2626`, 주의=주황 `#D97706`, 일반=초록 `#059669`) → 본문 좌: `ttk.Treeview` 목록(행 배경 긴급 `#FEF2F2`, 주의 `#FFFBEB`, 일반 흰색), 우: 선택한 건의 상세(`ReportView`)
- `ReportView`: 배너 + 긴급도 배지·요약 + 8개 섹션 카드 (메모 작성 탭과 공용)
- 일괄 처리 진행 중 `전체 처리`는 비활성; 완료 시 대시보드 새로고침, 메모 작성 탭의 최근 보고서도 새로고침

- [ ] **Step 1: 실패 테스트** (runner 동기, FakeClient):
  - `run_batch` 후 `dashboard_rows()` 정렬(긴급 먼저), `tile_counts()` 값
  - 같은 폴더 두 번째 `run_batch` → 건너뜀으로 `fake.calls` 증가 없음
  - 빈 폴더 → 상태 문구 `".txt 메모가 없습니다"`, API 호출 없음
  - 처리 중 `run_batch` 재호출 무시
  - `select_dashboard_row(0)` → `detail_status_text()`에 긴급도 이유 포함
- [ ] **Step 2–4:** FAIL → 구현 → 전체 PASS
- [ ] **Step 5:** 실제 API로 `참고/` 20건 일괄 처리 → 스크린샷으로 대시보드·상세 확인; 긴급도 판단이 메모 내용과 맞는지 점검(15 누유·07 설비점검·17 알람재발이 긴급인지 등은 **판단 확인용**이지 강제 아님)
- [ ] **Step 6:** README 갱신, `process.md` + commit `"feat: add batch dashboard to app"`, push
