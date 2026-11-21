from unittest.mock import AsyncMock, patch

import pytest
from pydantic_ai.exceptions import ModelHTTPError

from app.llm import run_with_gemini_fallback


@pytest.mark.anyio
async def test_gemini_503_retries_then_uses_fallback_model() -> None:
    calls: list[str] = []

    async def request(model: str) -> str:
        calls.append(model)
        if model == "primary":
            raise ModelHTTPError(status_code=503, model_name=model)
        return "fallback response"

    with patch("app.llm.asyncio.sleep", new_callable=AsyncMock):
        model, response = await run_with_gemini_fallback(
            "primary",
            ["fallback"],
            request,
            operation="test",
        )

    assert calls == ["primary", "primary", "fallback"]
    assert model == "fallback"
    assert response == "fallback response"
