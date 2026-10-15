"""문제 유형이 없는 이전 보고서들을 한 번의 API 호출로 분류한다."""
import json

from pydantic import BaseModel, Field

from handover.llm import call_structured
from handover.schema import CATEGORIES, UNCLASSIFIED, ModelCategory
from handover.store import Record, save_record

CLASSIFY_PROMPT = f"""생산 현장 교대 인수인계 보고서 요약 목록을 보고, 각 메모의 주된 문제 유형을 하나씩 고르세요.
유형: {", ".join(CATEGORIES)}.
여러 유형이 섞이면 다음 근무자가 가장 먼저 다뤄야 할 것을 고르세요. memo 값은 입력 그대로 쓰세요."""


class MemoCategory(BaseModel):
    memo: str = Field(description="입력의 memo 값 그대로")
    category: ModelCategory = Field(description="주된 문제 유형")


class Classification(BaseModel):
    items: list[MemoCategory]


def classify_missing(records: list[Record], client) -> int:
    """미분류 보고서만 분류해 저장하고, 바뀐 건수를 돌려준다."""
    # 같은 이름의 보고서가 여러 건일 수 있으므로(직접 입력 등) 이름별 목록으로 묶는다
    targets: dict[str, list[Record]] = {}
    for r in records:
        if r.report.category == UNCLASSIFIED:
            targets.setdefault(r.source_name, []).append(r)
    if not targets:
        return 0
    rows = [{"memo": name, "summary": rs[0].report.summary, "priority_reason": rs[0].report.priority_reason,
             "events": [i.text for i in rs[0].report.events]} for name, rs in targets.items()]
    content = "<reports>\n" + json.dumps(rows, ensure_ascii=False) + "\n</reports>"
    result = call_structured(client, CLASSIFY_PROMPT, content, Classification)
    changed = 0
    for item in result.items:
        for record in targets.get(item.memo, []):  # 목록에 없는 이름은 무시
            if record.report.category == UNCLASSIFIED:
                record.report.category = item.category
                save_record(record)
                changed += 1
    return changed
