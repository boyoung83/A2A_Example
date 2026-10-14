from types import SimpleNamespace

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


class FakeClient:
    """client.beta.messages.parse(**kw)만 흉내 내는 가짜 Anthropic client."""

    def __init__(self, stop_reason=None, parsed=None, results=None, error=None):
        self.calls = []
        self._error = error
        self._results = list(results) if results is not None else None
        self._single = (stop_reason, parsed)
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self._parse))

    def _parse(self, **kw):
        self.calls.append(kw)
        if self._error is not None:
            raise self._error
        stop_reason, parsed = self._results.pop(0) if self._results is not None else self._single
        return SimpleNamespace(stop_reason=stop_reason, parsed_output=parsed)
