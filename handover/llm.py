"""Claude API 호출: 구조화된 응답을 받아 Pydantic 모델로 돌려준다."""
from typing import TypeVar

import anthropic
import pydantic

from handover.prompt import SYSTEM_PROMPT, build_user_message
from handover.schema import HandoverReport

MODEL = "claude-opus-5-5"

T = TypeVar("T", bound=pydantic.BaseModel)


class ReportError(Exception):
    """보고서를 만들지 못했을 때 사용자에게 보여줄 오류."""


def call_structured(client, system: str, user_content: str, output_format: type[T]) -> T:
    try:
        response = client.beta.messages.parse(
            model=MODEL,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "medium"},
            system=system,
            messages=[{"role": "user", "content": user_content}],
            output_format=output_format,
        )
    except anthropic.AuthenticationError as e:
        raise ReportError("API 키가 올바르지 않습니다") from e
    except anthropic.APIConnectionError as e:
        raise ReportError("API 서버에 연결하지 못했습니다") from e
    except anthropic.APIStatusError as e:
        raise ReportError(f"API 오류 ({e.status_code})") from e
    except (pydantic.ValidationError, anthropic.APIError) as e:
        raise ReportError("응답 형식을 해석하지 못했습니다") from e

    if response.stop_reason == "refusal":
        raise ReportError("Claude가 요청을 거절했습니다")
    if response.stop_reason == "max_tokens":
        raise ReportError("응답이 잘렸습니다")
    if response.parsed_output is None:
        raise ReportError("응답 형식을 해석하지 못했습니다")
    return response.parsed_output


def summarize(memo: str, client) -> HandoverReport:
    return call_structured(client, SYSTEM_PROMPT, build_user_message(memo), HandoverReport)
