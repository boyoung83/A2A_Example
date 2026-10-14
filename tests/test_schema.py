from handover.schema import HandoverReport, Item, Unconfirmed


def test_report_roundtrip():
    r = HandoverReport(
        events=[Item(text="라벨 비뚤어짐", source_quote="08:40 포장 2호기 라벨이 자꾸 비뚤어짐.")],
        actions=[], current_status=[], next_checks=[],
        unconfirmed=[Unconfirmed(subject="원인", note="")],
    )
    assert HandoverReport.model_validate_json(r.model_dump_json()) == r
