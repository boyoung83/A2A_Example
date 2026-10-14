"""Claude가 채워 돌려줄 인수인계 보고서 구조."""
from pydantic import BaseModel, Field


class Item(BaseModel):
    text: str = Field(description="보고서에 들어갈 한 줄. 메모에 적힌 내용만 쓴다")
    source_quote: str = Field(description="이 항목의 근거가 된 원문 문장을 그대로 복사")


class Unconfirmed(BaseModel):
    subject: str = Field(description="확인되지 않은 대상 (예: 원인, 라벨 여분 수량)")
    note: str = Field(description="메모에 남은 관련 표현. 없으면 빈 문자열")


class HandoverReport(BaseModel):
    events: list[Item] = Field(description="메모에 기록된 발생 사건")
    actions: list[Item] = Field(description="실제로 수행한 조치")
    current_status: list[Item] = Field(description="교대 시점의 상태")
    next_checks: list[Item] = Field(description="다음 근무자가 확인할 일")
    unconfirmed: list[Unconfirmed] = Field(
        description="메모에서 확인되지 않았다고 했거나 기록이 없는 원인·수량·시각 등"
    )
