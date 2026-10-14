"""Claude API 호출: 메모 → HandoverReport."""
import anthropic
import pydantic

from handover.prompt import SYSTEM_PROMPT, build_user_message
from handover.schema import HandoverReport

MODEL = "claude-opus-5-5"


class ReportError(Exception):
    """보고서를 만들지 못했을 때 사용자에게 보여줄 오류."""


def summarize(memo: str, client) -> HandoverReport:
    try:
        response = client.beta.messages.parse(
            model=MODEL,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "medium"},
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_user_message(memo)}],
            output_format=HandoverReport,
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
