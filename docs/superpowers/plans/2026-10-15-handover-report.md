# 인수인계 보고서 생성기 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 작업 메모를 Claude API로 4개 항목 + 미확인 사항의 인수인계 보고서로 정리해 화면 출력·텍스트 저장하는 Python CLI.

**Architecture:** Claude에게 구조화된 출력(Pydantic `HandoverReport`)을 받고, 순수 함수 모듈(점검·렌더링)이 고정 양식 텍스트를 만든다. API 호출은 `llm.py` 한 곳에 모으고 테스트는 가짜 client로 대체해 API 없이 돌린다.

**Tech Stack:** Python 3.12, `anthropic`(Pydantic 포함), `pytest`

**Spec:** `docs/superpowers/specs/2026-10-15-handover-report-design.md`

## Global Constraints

- 모델 `claude-opus-5-5`, `output_config={"effort": "medium"}`, `max_tokens=16000`
- API 키는 `ANTHROPIC_API_KEY` 환경변수로만 받는다. 코드·파일에 키 금지
- 모든 파일 입출력 `encoding="utf-8"`; CLI 시작 시 `sys.stdout`/`sys.stderr`를 UTF-8로 reconfigure
- 보고서 항목 이름(정확히): `■ 발생한 일`, `■ 조치한 내용`, `■ 현재 상태`, `■ 다음 근무자 확인 사항`, `■ 미확인 사항`
- 빈 항목 표기: `- 메모에 기록 없음` / 미확인 표기: `- {subject}: 미확인` (+ note 있으면 ` ({note})`)
- 저장 경로: `reports/인수인계_<원본이름>_<YYYYMMDD_HHMMSS>.txt` (붙여넣기 입력은 원본이름 `입력`)
- 자동 점검은 경고만 하고 저장을 막지 않는다

## Review Focus

1. 공백뿐인 메모 → API를 호출하지 않고 "메모가 비어 있습니다" 안내, 종료코드 2 (Task 5 테스트)
2. 숫자가 전혀 없는 메모(작업메모_03) → 점검이 거짓 경고를 내지 않음 (Task 2 테스트)
3. 근거 문장이 원문과 줄바꿈·공백만 다름 → 일치로 판정 (Task 2 테스트)
4. 같은 원본을 같은 초에 두 번 저장 → 덮어쓰지 않고 `_2` 붙임 (Task 5 테스트)
5. `--dir` 처리 중 한 파일 API 실패 → 나머지는 계속 처리, 종료코드 1 (Task 5 테스트)

---

### Task 1: 프로젝트 준비 + 스키마

**Files:**
- Create: `requirements.txt`, `handover/__init__.py`, `handover/schema.py`, `tests/test_schema.py`, `.gitignore`

**Interfaces:**
- Produces:
  - `class Item(BaseModel): text: str; source_quote: str`
  - `class Unconfirmed(BaseModel): subject: str; note: str`
  - `class HandoverReport(BaseModel): events: list[Item]; actions: list[Item]; current_status: list[Item]; next_checks: list[Item]; unconfirmed: list[Unconfirmed]`
  - 각 필드에 `Field(description=...)`로 한글 설명(모델이 읽음): events="메모에 기록된 발생 사건", actions="실제로 수행한 조치", current_status="교대 시점의 상태", next_checks="다음 근무자가 확인할 일", unconfirmed="메모에서 확인되지 않았다고 했거나 기록이 없는 원인·수량·시각 등"; source_quote="이 항목의 근거가 된 원문 문장을 그대로 복사"

- [ ] **Step 1:** `git init` (폴더가 git 저장소가 아님 — 커밋 단계용, Claude의 판단). `.gitignore`에 `reports/`, `__pycache__/`, `.venv/`
- [ ] **Step 2:** `requirements.txt` = `anthropic` / `pytest`; 실행 `python -m pip install -r requirements.txt` → 성공
- [ ] **Step 3: 실패 테스트** `tests/test_schema.py`

```python
def test_report_roundtrip():
    r = HandoverReport(events=[Item(text="라벨 비뚤어짐", source_quote="08:40 포장 2호기 라벨이 자꾸 비뚤어짐.")],
                       actions=[], current_status=[], next_checks=[],
                       unconfirmed=[Unconfirmed(subject="원인", note="")])
    assert HandoverReport.model_validate_json(r.model_dump_json()) == r
```

- [ ] **Step 4:** `pytest tests/test_schema.py -v` → FAIL(import error)
- [ ] **Step 5:** `handover/schema.py` 구현
- [ ] **Step 6:** `pytest tests/test_schema.py -v` → PASS
- [ ] **Step 7:** `git add . && git commit -m "feat: add report schema"`

### Task 2: 환각 자동 점검

**Files:** Create `handover/checks.py`, `tests/test_checks.py`

**Interfaces:**
- Consumes: `HandoverReport`, `Item`, `Unconfirmed` (Task 1)
- Produces:
  - `extract_numbers(text: str) -> set[str]` — 정규식 `\d{1,2}:\d{2}|\d+` (시각을 먼저 매칭)
  - `check_report(report: HandoverReport, memo: str) -> list[str]` — 경고 문장 목록, 이상 없으면 `[]`
  - `RESOLUTION_WORDS = ["해결", "완료", "정상화", "이상 없음", "문제없"]`

점검 규칙 (검사 대상 = 모든 `Item.text`, `Unconfirmed.subject`, `Unconfirmed.note`; `source_quote`는 숫자 검사 제외):
1. 숫자/시각이 `extract_numbers(memo)`에 없으면 → `"원문에 없는 숫자 '{n}': {문장}"`
2. `source_quote`를 공백 정규화(`" ".join(s.split())`)했을 때 정규화된 memo의 부분 문자열이 아니면 → `"근거 문장이 원문에 없음: {quote}"`
3. `RESOLUTION_WORDS` 중 memo에 없는 단어가 문장에 있으면 → `"원문에 없는 단정 표현 '{w}': {문장}"`

- [ ] **Step 1: 실패 테스트** (`MEMO01` = `참고/작업메모_01_라벨이상.txt` 내용을 테스트 상수로 복사)

```python
def test_times_extracted_whole():
    assert extract_numbers("08:40 라벨, 20개") == {"08:40", "20"}

def test_invented_quantity_flagged():
    r = report_with(next_checks=[Item(text="라벨 여분 10장 확인", source_quote="라벨 여분 얼마 안 남음.")])
    assert any("'10'" in w for w in check_report(r, MEMO01))

def test_resolution_word_flagged():
    r = report_with(current_status=[Item(text="센서 청소로 문제 해결", source_quote="09:10 센서 주변 청소하고 재가동.")])
    assert any("'해결'" in w for w in check_report(r, MEMO01))

def test_fake_quote_flagged():
    r = report_with(events=[Item(text="라벨 비뚤어짐", source_quote="라벨 기계가 고장남")])
    assert any("근거 문장이 원문에 없음" in w for w in check_report(r, MEMO01))

def test_quote_whitespace_insensitive():
    r = report_with(events=[Item(text="라벨 비뚤어짐", source_quote="08:40  포장 2호기\n라벨이 자꾸 비뚤어짐.")])
    assert check_report(r, MEMO01) == []

def test_no_numbers_memo_clean():  # 작업메모_03
    memo = "오후에 1호기에서 소리가 좀 이상했음.\n다음 근무자가 확인해줬으면 함."
    r = report_with(events=[Item(text="1호기 이상 소음", source_quote="오후에 1호기에서 소리가 좀 이상했음.")],
                    unconfirmed=[Unconfirmed(subject="발생 시각", note="")])
    assert check_report(r, memo) == []
```

`report_with(**kw)`는 테스트 파일 내 헬퍼: 지정 안 한 필드는 `[]`.

- [ ] **Step 2:** `pytest tests/test_checks.py -v` → FAIL
- [ ] **Step 3:** `handover/checks.py` 구현
- [ ] **Step 4:** `pytest tests/test_checks.py -v` → PASS
- [ ] **Step 5:** commit `"feat: add hallucination checks"`

### Task 3: 보고서 렌더링

**Files:** Create `handover/render.py`, `tests/test_render.py`

**Interfaces:**
- Consumes: `HandoverReport` (Task 1)
- Produces: `render_report(report: HandoverReport, memo: str, source_name: str, created_at: datetime, warnings: list[str]) -> str`

양식은 spec의 "보고서 양식" 그대로. 헤더 줄 `" 작성: {created_at:%Y-%m-%d %H:%M} / 원문: {source_name}"`. 경고가 없으면 `※ 자동 점검: 이상 없음`, 있으면 `※ 자동 점검 경고 (원문과 대조해 확인하세요)` 다음에 `- {w}` 줄들. 마지막에 `[원문 메모]` + memo 원문.

- [ ] **Step 1: 실패 테스트**

```python
def test_section_order_and_empty():
    out = render_report(empty_report(), "메모", "a.txt", datetime(2026,10,15,14,30), [])
    heads = ["■ 발생한 일", "■ 조치한 내용", "■ 현재 상태", "■ 다음 근무자 확인 사항", "■ 미확인 사항"]
    assert [out.index(h) for h in heads] == sorted(out.index(h) for h in heads)
    assert out.count("- 메모에 기록 없음") == 5
    assert "작성: 2026-10-15 14:30 / 원문: a.txt" in out
    assert "※ 자동 점검: 이상 없음" in out

def test_unconfirmed_format():
    r = empty_report(); r.unconfirmed = [Unconfirmed(subject="라벨 여분 수량", note="메모에 '얼마 안 남음'만 기록"),
                                         Unconfirmed(subject="원인", note="")]
    out = render_report(r, "메모", "a.txt", datetime(2026,10,15), [])
    assert "- 라벨 여분 수량: 미확인 (메모에 '얼마 안 남음'만 기록)" in out
    assert "- 원인: 미확인\n" in out

def test_warnings_and_memo_appended():
    out = render_report(empty_report(), "원문내용", "a.txt", datetime(2026,10,15), ["원문에 없는 숫자 '10': x"])
    assert "- 원문에 없는 숫자 '10': x" in out
    assert out.rstrip().endswith("원문내용") and "[원문 메모]" in out
```

- [ ] **Step 2:** `pytest tests/test_render.py -v` → FAIL
- [ ] **Step 3:** 구현
- [ ] **Step 4:** PASS 확인
- [ ] **Step 5:** commit `"feat: add report renderer"`

### Task 4: 프롬프트 + Claude API 호출

**Files:** Create `handover/prompt.py`, `handover/llm.py`, `tests/test_llm.py`

**Interfaces:**
- Consumes: `HandoverReport` (Task 1)
- Produces:
  - `SYSTEM_PROMPT: str`, `build_user_message(memo: str) -> str` (memo를 `<memo>\n...\n</memo>`로 감쌈)
  - `MODEL = "claude-opus-5-5"`
  - `class ReportError(Exception)`
  - `summarize(memo: str, client) -> HandoverReport`

`SYSTEM_PROMPT` (고정 문구):

```
당신은 생산 현장의 교대 인수인계 보고서를 작성합니다. 읽는 사람은 다음 교대 근무자이며, 이 보고서만 보고 무엇이 조치됐고 무엇을 직접 확인해야 하는지 판단합니다.

메모를 다음 항목으로 나누세요: 발생한 일(events), 조치한 내용(actions), 현재 상태(current_status), 다음 근무자 확인 사항(next_checks), 미확인 사항(unconfirmed).

반드시 지킬 규칙:
1. 메모에 적힌 내용만 쓰세요. 원인, 수량, 시각, 담당자, 결과를 추측하거나 채워 넣지 마세요.
2. 시각과 숫자는 원문 그대로 쓰세요. "4시쯤"처럼 불확실한 표현은 불확실한 그대로 두세요.
3. 일부만 확인한 결과를 전체로 넓히지 마세요. "20개 확인했는데 정상"은 "20개 확인 결과 정상"이며 "문제 해결"이 아닙니다.
4. 메모에 "모름", "확인 못 함", "아직", "확정 아님", "못 셈"으로 적힌 것, 그리고 다음 근무자에게 필요한데 메모에 없는 원인·수량·시각은 unconfirmed에 넣으세요.
5. 전화로만 전달받음, 서류 미수령처럼 공식 확인 전인 정보는 그 사실을 함께 적으세요.
6. 각 항목의 source_quote에는 근거가 된 원문 문장을 한 글자도 바꾸지 말고 복사하세요.
7. 메모에 해당 내용이 없는 항목은 빈 목록으로 두세요.
```

`summarize` 호출 형태:

```python
client.beta.messages.parse(
    model=MODEL, max_tokens=16000,
    betas=["server-side-fallback-2026-07-01"], fallbacks="default",
    output_config={"effort": "medium"},
    system=SYSTEM_PROMPT,
    messages=[{"role": "user", "content": build_user_message(memo)}],
    output_format=HandoverReport,
)
```

`stop_reason == "refusal"` → `ReportError("Claude가 요청을 거절했습니다")`, `"max_tokens"` → `ReportError("응답이 잘렸습니다")`, `parsed_output is None` → `ReportError("응답 형식을 해석하지 못했습니다")`. `anthropic.AuthenticationError` → `ReportError("API 키가 올바르지 않습니다")`, `anthropic.APIConnectionError` → `ReportError("API 서버에 연결하지 못했습니다")`, 그 외 `anthropic.APIStatusError` → `ReportError(f"API 오류 ({e.status_code})")`.

- [ ] **Step 1: 실패 테스트** — 가짜 client `FakeClient(stop_reason=None, parsed=None, results=None)`: `.beta.messages.parse(**kw)`가 `kw`를 `self.calls`에 기록하고 `SimpleNamespace(stop_reason=..., parsed_output=...)`를 반환. `results`(`(stop_reason, parsed)` 목록)를 주면 호출마다 순서대로 소비

```python
def test_summarize_returns_parsed():
    fake = FakeClient(stop_reason="end_turn", parsed=SAMPLE_REPORT)
    assert summarize("메모A", fake) == SAMPLE_REPORT
    kw = fake.calls[0]
    assert kw["model"] == "claude-opus-5-5" and kw["output_format"] is HandoverReport
    assert "메모A" in kw["messages"][0]["content"] and "미확인" in kw["system"]

def test_refusal_raises():
    with pytest.raises(ReportError, match="거절"):
        summarize("메모", FakeClient(stop_reason="refusal", parsed=None))

def test_unparsed_raises():
    with pytest.raises(ReportError):
        summarize("메모", FakeClient(stop_reason="end_turn", parsed=None))
```

- [ ] **Step 2:** `pytest tests/test_llm.py -v` → FAIL
- [ ] **Step 3:** `prompt.py`, `llm.py` 구현
- [ ] **Step 4:** PASS 확인
- [ ] **Step 5: SDK 확인** — `python -c "import anthropic, inspect; print(anthropic.__version__); print('fallbacks' in inspect.signature(anthropic.Anthropic().beta.messages.parse).parameters)"` (가짜 키 `ANTHROPIC_API_KEY=x`로 실행). `False`면 `fallbacks`/`betas`를 빼고 `client.messages.parse`로 바꾼 뒤 테스트를 맞추고 계획 대비 변경으로 보고
- [ ] **Step 6:** commit `"feat: add Claude summarize call"`

### Task 5: CLI (입력·출력·저장)

**Files:** Create `handover_report.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `summarize`, `ReportError` (Task 4), `check_report` (Task 2), `render_report` (Task 3)
- Produces:
  - `main(argv: list[str] | None = None, client=None) -> int` — `client`가 None이면 `anthropic.Anthropic()` 생성(키 없으면 안내 후 2 반환)
  - `read_memo_interactive(stream: TextIO) -> str` — 빈 줄 두 번 연속 또는 EOF에서 종료
  - `save_report(text: str, out_dir: Path, source_stem: str, now: datetime) -> Path` — 같은 이름 존재 시 `_2`, `_3` …

인자: `--file PATH`, `--dir PATH`(정렬된 `*.txt` 각각 처리), `--out DIR`(기본 `reports`). 둘 다 없으면 안내 문구 `"메모를 붙여넣고 빈 줄에서 Enter를 두 번 누르세요."` 후 대화형 입력. 처리 순서: 메모 → `summarize` → `check_report` → `render_report` → 화면 출력 → `save_report` → `"저장됨: {path}"` 출력. 종료코드: 성공 0, 입력 오류(빈 메모·파일 없음·키 없음) 2, `--dir`에서 하나라도 실패 1.

- [ ] **Step 1: 실패 테스트** (Task 4의 `FakeClient`, `SAMPLE_REPORT`를 `tests/conftest.py`로 옮겨 재사용)

```python
def test_file_mode_prints_and_saves(tmp_path, capsys):
    memo = tmp_path / "m.txt"; memo.write_text("08:40 라벨 비뚤어짐.", encoding="utf-8")
    assert main(["--file", str(memo), "--out", str(tmp_path / "r")], client=FakeClient("end_turn", SAMPLE_REPORT)) == 0
    saved = list((tmp_path / "r").glob("인수인계_m_*.txt"))
    assert len(saved) == 1 and "■ 발생한 일" in saved[0].read_text(encoding="utf-8")
    assert "■ 발생한 일" in capsys.readouterr().out

def test_blank_memo_no_api_call(tmp_path):
    memo = tmp_path / "m.txt"; memo.write_text("  \n\n", encoding="utf-8")
    fake = FakeClient("end_turn", SAMPLE_REPORT)
    assert main(["--file", str(memo)], client=fake) == 2 and fake.calls == []

def test_save_no_overwrite(tmp_path):
    now = datetime(2026, 10, 15, 14, 30, 0)
    a = save_report("A", tmp_path, "m", now); b = save_report("B", tmp_path, "m", now)
    assert a != b and b.name.endswith("_2.txt") and a.read_text(encoding="utf-8") == "A"

def test_dir_continues_after_failure(tmp_path):
    for n in ("a", "b"): (tmp_path / f"{n}.txt").write_text("메모", encoding="utf-8")
    fake = FakeClient(results=[("refusal", None), ("end_turn", SAMPLE_REPORT)])
    assert main(["--dir", str(tmp_path), "--out", str(tmp_path / "r")], client=fake) == 1
    assert len(list((tmp_path / "r").glob("*.txt"))) == 1

def test_interactive_reader_stops_at_double_blank():
    assert read_memo_interactive(io.StringIO("줄1\n\n줄2\n\n\n무시")) == "줄1\n\n줄2"
```

- [ ] **Step 2:** `pytest tests/test_cli.py -v` → FAIL
- [ ] **Step 3:** 구현
- [ ] **Step 4:** `pytest -v` 전체 → PASS
- [ ] **Step 5:** commit `"feat: add CLI"`

### Task 6: README + 실제 API 검증

**Files:** Create `README.md`

README 내용: ① 설치 `python -m pip install -r requirements.txt` ② 키 설정 PowerShell `$env:ANTHROPIC_API_KEY="sk-ant-..."` (영구 설정은 `setx ANTHROPIC_API_KEY "..."` 후 새 창) ③ 실행 예 `python handover_report.py`, `python handover_report.py --file 참고\작업메모_01_라벨이상.txt`, `python handover_report.py --dir 참고` ④ 보고서 양식과 자동 점검 경고의 의미 ⑤ 테스트 `python -m pytest`.

- [ ] **Step 1:** README 작성
- [ ] **Step 2: 실제 실행** (API 키 필요, 20건 × Opus 비용 발생 — 사용자 확인 후) `python handover_report.py --dir 참고`
- [ ] **Step 3: 결과 점검** — 아래가 모두 맞아야 통과. 틀리면 `SYSTEM_PROMPT` 수정 후 해당 메모만 재실행
  - 01: "해결" 표현 없음, "20개 확인 결과 정상"으로 한정, 원인·라벨 여분 수량 = 미확인, 라벨 수량 숫자 없음
  - 03: 시각 지어내지 않음, 발생 시점·현재 지속 여부 = 미확인
  - 09: 도착 "오후 4시쯤, 확정 아님"으로 표기, 실제 도착 = 미확인
  - 12: 80개 변경은 전화 전달·수정 지시서 미수령으로 표기
  - 20: 고객사 출발 = 미확인, "출하 완료"로 쓰지 않음
  - 모든 보고서의 자동 점검 경고를 열어 실제 오류인지 확인
- [ ] **Step 4:** commit `"docs: add README"`
