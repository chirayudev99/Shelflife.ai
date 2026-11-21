import pytest
from pydantic import ValidationError

from app.schemas.chat import CreateThreadRequest, StreamRequest


def _text_message(text: str = "question") -> dict[str, object]:
    return {"role": "user", "parts": [{"type": "text", "text": text}]}


def test_stream_request_bounds_message_count() -> None:
    request = {
        "threadId": "00000000-0000-0000-0000-000000000001",
        "messages": [_text_message() for _ in range(101)],
    }

    with pytest.raises(ValidationError):
        StreamRequest.model_validate(request)


def test_stream_request_bounds_text_length() -> None:
    request = {
        "threadId": "00000000-0000-0000-0000-000000000001",
        "messages": [_text_message("x" * 12_001)],
    }

    with pytest.raises(ValidationError):
        StreamRequest.model_validate(request)


def test_thread_title_is_limited_to_database_column_length() -> None:
    with pytest.raises(ValidationError):
        CreateThreadRequest(title="x" * 256)


def test_follow_up_allows_empty_history_parts_but_requires_latest_user_text() -> None:
    request = {
        "threadId": "00000000-0000-0000-0000-000000000001",
        "messages": [
            {"role": "assistant", "parts": []},
            _text_message("follow-up"),
        ],
    }

    validated = StreamRequest.model_validate(request)
    assert validated.messages[0].parts == []

    request["messages"][-1] = _text_message("   ")
    with pytest.raises(ValidationError, match="latest user message"):
        StreamRequest.model_validate(request)
