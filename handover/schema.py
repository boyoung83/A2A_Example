"""Claude가 채워 돌려줄 인수인계 보고서 구조.

필드 순서가 곧 모델이 쓰는 순서다: 내용을 먼저 정리하고 긴급도 판단은 마지막에 한다.
"""
from typing import Literal

from pydantic import BaseModel, Field

Priority = Literal["긴급", "주의", "일반"]
PRIORITY_ORDER: list[str] = ["긴급", "주의", "일반"]

# 메모의 주된 문제 유형 (대시보드 원형 그래프용). '미분류'는 유형이 없던 이전 보고서에만 쓴다.
CATEGORIES: list[str] = ["설비 이상", "수량 불일치", "품질·검사", "라벨·식별", "안전",
                         "자재·물류", "서류·전산", "작업 지시·일정", "정상·기록"]
UNCLASSIFIED = "미분류"
ModelCategory = Literal["설비 이상", "수량 불일치", "품질·검사", "라벨·식별", "안전",
                        "자재·물류", "서류·전산", "작업 지시·일정", "정상·기록"]
Category = Literal["설비 이상", "수량 불일치", "품질·검사", "라벨·식별", "안전",
                   "자재·물류", "서류·전산", "작업 지시·일정", "정상·기록", "미분류"]


class Item(BaseModel):
    text: str = Field(description="보고서에 들어갈 한 줄. 메모에 적힌 내용만 쓴다")
    source_quote: str = Field(description="이 항목의 근거가 된 원문 문장을 그대로 복사")


class TimelineEntry(BaseModel):
    time: str = Field(description="메모에 적힌 시각 표기 그대로 (예: 08:40, 오후)")
    text: str = Field(description="그 시각에 있었던 일")
    source_quote: str = Field(description="근거가 된 원문 문장을 그대로 복사")


class Fact(BaseModel):
    label: str = Field(description="대상 (예: 대기 제품 수량, 주문 번호, 설비)")
    value: str = Field(description="원문 표기 그대로의 값 (예: 12개, O-202, 포장 2호기)")
    source_quote: str = Field(description="근거가 된 원문 문장을 그대로 복사")


class Contact(BaseModel):
    party: str = Field(description="전달·요청한 상대 (예: 설비팀, 품질 담당자)")
    request: str = Field(description="무엇을 전달·요청했는지")
    status: str = Field(description="회신·처리 상태. 메모에 없으면 '회신 여부 미기록'")
    source_quote: str = Field(description="근거가 된 원문 문장을 그대로 복사")


class Unconfirmed(BaseModel):
    subject: str = Field(description="확인되지 않은 대상 (예: 원인, 라벨 여분 수량)")
    note: str = Field(description="메모에 남은 관련 표현. 없으면 빈 문자열")


class HandoverReport(BaseModel):
    summary: str = Field(description="다음 근무자가 가장 먼저 알아야 할 핵심 한 문장")
    events: list[Item] = Field(description="메모에 기록된 발생 사건")
    actions: list[Item] = Field(description="실제로 수행한 조치")
    current_status: list[Item] = Field(description="교대 시점의 상태")
    next_checks: list[Item] = Field(description="다음 근무자가 확인할 일")
    timeline: list[TimelineEntry] = Field(description="메모에 시각이 적힌 기록만 시간 순서로")
    key_facts: list[Fact] = Field(description="설비·라인·주문·LOT·제품과 수량 (원문 표기 그대로)")
    contacts: list[Contact] = Field(description="전달·요청한 상대와 회신 상태")
    unconfirmed: list[Unconfirmed] = Field(
        description="메모에서 확인되지 않았다고 했거나 기록이 없는 원인·수량·시각 등"
    )
    category: Category = Field(description="메모의 주된 문제 유형 하나 ('미분류'는 쓰지 않는다)")
    priority_reason: str = Field(description="긴급도를 그렇게 판단한 메모 속 근거 한 문장")
    priority: Priority = Field(description="긴급 / 주의 / 일반")
