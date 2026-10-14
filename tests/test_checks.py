from handover.checks import check_report, extract_numbers
from handover.schema import HandoverReport, Item, Unconfirmed

MEMO01 = """08:40 포장 2호기 라벨이 자꾸 비뚤어짐.
09:10 센서 주변 청소하고 재가동.
이후 20개 확인했는데 정상. 원인은 아직 모름.
오후조에서 다시 확인 필요. 라벨 여분 얼마 안 남음. 수량은 못 셈."""


def report_with(**kw):
    fields = dict(events=[], actions=[], current_status=[], next_checks=[], unconfirmed=[])
    fields.update(kw)
    return HandoverReport(**fields)


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
