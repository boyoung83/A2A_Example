"""처리된 보고서 전체에서 공통점·인사이트를 뽑는다 (API 한 번 호출)."""
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pydantic
from pydantic import BaseModel, Field

from handover.llm import ReportError, call_structured
from handover.store import Record

INSIGHTS_FILE = "insights.json"

INSIGHT_PROMPT = """당신은 생산 현장 교대 인수인계 보고서 여러 건을 함께 읽고, 다음 근무조와 관리자가 알아야 할 공통점과 인사이트를 정리합니다.

입력은 보고서별 요약(JSON 목록)입니다. 다음을 지키세요:
1. 입력에 있는 내용만 근거로 쓰세요. 입력에 없는 원인·수량·설비·담당자를 지어내지 마세요.
2. 모든 항목의 related에는 근거가 된 메모 이름(memo 값)을 정확히 그대로 넣으세요. 근거가 한 건뿐이면 공통 패턴으로 쓰지 마세요.
3. patterns: 여러 건에 반복되는 공통점 (같은 부서 회신 대기, 같은 유형의 설비 이상, 수량 불일치 반복 등)
4. risks: 긴급 건을 중심으로 다음 근무조가 특히 주의할 경향이나 겹치는 위험
5. gaps: 보고서에서 반복적으로 '미확인'이 된 정보처럼, 메모를 쓸 때 보완하면 좋을 점
6. headline: 전체를 한 문장으로 요약하세요.
7. 각 목록은 중요한 것부터 최대 4개까지 쓰세요. 해당하는 내용이 없으면 빈 목록으로 두세요."""


class InsightPoint(BaseModel):
    title: str = Field(description="짧은 제목")
    detail: str = Field(description="한두 문장 설명")
    related: list[str] = Field(description="근거가 된 메모 이름 목록 (입력의 memo 값 그대로)")


class Insights(BaseModel):
    headline: str = Field(description="전체를 한 문장으로 요약")
    patterns: list[InsightPoint] = Field(description="여러 건에 반복되는 공통점")
    risks: list[InsightPoint] = Field(description="다음 근무조가 특히 주의할 경향·위험")
    gaps: list[InsightPoint] = Field(description="반복적으로 미확인된 정보 등 기록 보완점")


def build_insight_input(records: list[Record]) -> str:
    rows = [{
        "memo": r.source_name,
        "priority": r.report.priority,
        "reason": r.report.priority_reason,
        "summary": r.report.summary,
        "events": [i.text for i in r.report.events],
        "unconfirmed": [u.subject for u in r.report.unconfirmed],
        "contacts": [f"{c.party} — {c.request} — {c.status}" for c in r.report.contacts],
    } for r in records]
    return json.dumps(rows, ensure_ascii=False)


def extract_insights(records: list[Record], client) -> Insights:
    if not records:
        raise ReportError("분석할 보고서가 없습니다")
    content = "다음 보고서들의 공통점과 인사이트를 정리하세요.\n\n<reports>\n" \
              + build_insight_input(records) + "\n</reports>"
    insights = call_structured(client, INSIGHT_PROMPT, content, Insights)
    known = {r.source_name for r in records}
    for point in insights.patterns + insights.risks + insights.gaps:
        point.related = [name for name in point.related if name in known]  # 지어낸 메모 이름은 버린다
    return insights


def _signature(records: list[Record]) -> list[str]:
    return sorted(f"{r.source_name}|{r.created_at.isoformat()}" for r in records)


@dataclass
class InsightSnapshot:
    insights: Insights
    created_at: datetime
    source_count: int
    signature: list[str]

    def is_current(self, records: list[Record]) -> bool:
        return self.signature == _signature(records)


def save_insights(out_dir: Path, insights: Insights, records: list[Record], now: datetime) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / INSIGHTS_FILE
    data = {"created_at": now.isoformat(), "source_count": len(records),
            "signature": _signature(records), "insights": insights.model_dump()}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_insights(out_dir: Path) -> InsightSnapshot | None:
    try:
        data = json.loads((out_dir / INSIGHTS_FILE).read_text(encoding="utf-8"))
        return InsightSnapshot(Insights.model_validate(data["insights"]), datetime.fromisoformat(data["created_at"]),
                               int(data["source_count"]), list(data["signature"]))
    except (OSError, ValueError, KeyError, TypeError, pydantic.ValidationError):
        return None
