from types import SimpleNamespace

from handover.insights import Insights
from handover.schema import HandoverReport, Item


def make_report(**kw) -> HandoverReport:
    fields = dict(summary="", events=[], actions=[], current_status=[], next_checks=[],
                  timeline=[], key_facts=[], contacts=[], unconfirmed=[],
                  priority_reason="", priority="일반")
    fields.update(kw)
    return HandoverReport(**fields)


SAMPLE_REPORT = make_report(
    summary="라벨 비뚤어짐",
    events=[Item(text="08:40 라벨 비뚤어짐", source_quote="08:40 라벨 비뚤어짐.")],
    priority_reason="라벨 비뚤어짐 기록",
)


EMPTY_INSIGHTS = Insights(headline="", patterns=[], risks=[], gaps=[])


class FakeClient:
    """client.beta.messages.parse(**kw)만 흉내 내는 가짜 Anthropic client.

    보고서 요청(HandoverReport)은 calls, 인사이트 요청(Insights)은 insight_calls에 따로 기록한다.
    인사이트 응답은 insights 인자로 정하고, 없으면 단일 응답이 Insights일 때 그것을, 아니면 빈 인사이트를 준다.
    """

    def __init__(self, stop_reason=None, parsed=None, results=None, error=None, insights=None):
        self.calls = []
        self.insight_calls = []
        self._error = error
        self._results = list(results) if results is not None else None
        self._single = (stop_reason, parsed)
        self._insights = insights
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self._parse))

    def _parse(self, **kw):
        if kw.get("output_format") is Insights:
            self.insight_calls.append(kw)
            if self._error is not None:
                raise self._error
            if self._insights is not None:
                return SimpleNamespace(stop_reason="end_turn", parsed_output=self._insights)
            stop_reason, parsed = self._single
            if parsed is None or isinstance(parsed, Insights):
                return SimpleNamespace(stop_reason=stop_reason, parsed_output=parsed)
            return SimpleNamespace(stop_reason="end_turn", parsed_output=EMPTY_INSIGHTS)
        self.calls.append(kw)
        if self._error is not None:
            raise self._error
        stop_reason, parsed = self._results.pop(0) if self._results is not None else self._single
        return SimpleNamespace(stop_reason=stop_reason, parsed_output=parsed)
