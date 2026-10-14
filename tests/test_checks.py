from conftest import make_report
from handover.checks import check_report, extract_numbers
from handover.schema import Contact, Fact, Item, TimelineEntry, Unconfirmed

MEMO01 = """08:40 포장 2호기 라벨이 자꾸 비뚤어짐.
09:10 센서 주변 청소하고 재가동.
이후 20개 확인했는데 정상. 원인은 아직 모름.
오후조에서 다시 확인 필요. 라벨 여분 얼마 안 남음. 수량은 못 셈."""


report_with = make_report


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
    r = report_with(
        events=[Item(text="1호기 이상 소음", source_quote="오후에 1호기에서 소리가 좀 이상했음.")],
        unconfirmed=[Unconfirmed(subject="발생 시각", note="")],
    )
    assert check_report(r, memo) == []


def test_hedged_resolution_not_flagged():  # live 01 / 05 phrasings
    r = report_with(actions=[
        Item(text="재가동 이후 20개 확인 결과 정상 (20개만 확인, 문제 해결 여부는 확정 아님)", source_quote="이후 20개 확인했는데 정상."),
        Item(text="20개 재확인 결과 정상 (문제 해결이 확인된 것은 아님)", source_quote="이후 20개 확인했는데 정상."),
    ])
    assert check_report(r, MEMO01) == []


def test_unconfirmed_not_checked_for_resolution_words():  # live 10 phrasing
    r = report_with(unconfirmed=[Unconfirmed(subject="라벨 재부착 완료 시각", note="")])
    assert check_report(r, MEMO01) == []


def test_spacing_variants_flagged():
    for text in ("라벨 문제 없음", "라벨 이상없음"):
        r = report_with(current_status=[Item(text=text, source_quote="이후 20개 확인했는데 정상.")])
        assert any("단정 표현" in w for w in check_report(r, MEMO01)), text


def test_timeline_invented_time_flagged():
    r = report_with(timeline=[TimelineEntry(time="10:30", text="재가동", source_quote="09:10 센서 주변 청소하고 재가동.")])
    assert any("'10:30'" in w for w in check_report(r, MEMO01))


def test_fact_invented_value_flagged():
    r = report_with(key_facts=[Fact(label="라벨 여분", value="15개", source_quote="라벨 여분 얼마 안 남음.")])
    assert any("'15'" in w for w in check_report(r, MEMO01))


def test_contact_fake_quote_flagged():
    r = report_with(contacts=[Contact(party="설비팀", request="점검", status="회신 없음", source_quote="설비팀에 연락함")])
    assert any("근거 문장이 원문에 없음" in w for w in check_report(r, MEMO01))


def test_summary_resolution_flagged():
    r = report_with(summary="라벨 문제 해결됨")
    assert any("'해결'" in w for w in check_report(r, MEMO01))


def test_priority_reason_invented_number_flagged():
    r = report_with(priority_reason="라벨 3장만 남아 긴급")
    assert any("'3'" in w for w in check_report(r, MEMO01))


def test_detailed_clean_report_has_no_warnings():
    r = report_with(
        summary="포장 2호기 라벨 비뚤어짐, 원인 미확인",
        timeline=[TimelineEntry(time="08:40", text="라벨 비뚤어짐 발견", source_quote="08:40 포장 2호기 라벨이 자꾸 비뚤어짐.")],
        key_facts=[Fact(label="재가동 후 확인 수량", value="20개", source_quote="이후 20개 확인했는데 정상.")],
        contacts=[Contact(party="오후조", request="재확인", status="회신 여부 미기록", source_quote="오후조에서 다시 확인 필요.")],
        priority="주의", priority_reason="원인이 아직 확인되지 않음",
    )
    assert check_report(r, MEMO01) == []
