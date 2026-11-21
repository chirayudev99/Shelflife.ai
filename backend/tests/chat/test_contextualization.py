from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.genai import errors

from app.chat.contextualization import contextualize_query, detect_companies
from app.chat.orchestrator import _retrieve_passages
from app.schemas.chat import TextPart, UIMessage


def _message(role: str, text: str) -> UIMessage:
    return UIMessage(role=role, parts=[TextPart(text=text)])


def _mock_client(response: str | None = None, *, failure: Exception | None = None):
    models = SimpleNamespace(
        generate_content=AsyncMock(
            return_value=SimpleNamespace(text=response),
            side_effect=failure,
        )
    )
    aio = SimpleNamespace(models=models, aclose=AsyncMock())
    return SimpleNamespace(aio=aio, close=MagicMock())


@pytest.mark.anyio
async def test_contextualizer_uses_only_two_prior_turns_and_returns_rewrite() -> None:
    messages = [
        _message("user", "Very old question"),
        _message("assistant", "Very old answer"),
        _message("user", "Older unrelated question"),
        _message("assistant", "Older unrelated answer"),
        _message("user", "Compare Blinkit and Swiggy margins"),
        _message("assistant", "Blinkit and Swiggy margin results"),
        _message("user", "Add Zepto to that"),
    ]
    client = _mock_client("Compare Blinkit, Swiggy Instamart, and Zepto UDRHP margins.")

    with patch("app.chat.contextualization.genai.Client", return_value=client):
        query = await contextualize_query("Add Zepto to that", messages)

    request = client.aio.models.generate_content.await_args.kwargs
    assert request["model"] == "gemini-3.5-flash-lite"
    assert request["config"].max_output_tokens == 120
    assert "Very old question" not in request["contents"]
    assert "Older unrelated question" in request["contents"]
    assert "Compare Blinkit and Swiggy margins" in request["contents"]
    assert "Add Zepto to that" in request["contents"]
    assert query == "Compare Blinkit, Swiggy Instamart, and Zepto UDRHP margins."
    client.aio.aclose.assert_awaited_once()


@pytest.mark.anyio
async def test_unchanged_followup_inherits_prior_metrics_and_companies() -> None:
    messages = [
        _message(
            "user",
            "Compare Blinkit and Swiggy dark-store expansion and contribution margins",
        ),
        _message(
            "assistant", "The comparison covers expansion and contribution margins."
        ),
        _message("user", "What about Zepto?"),
    ]
    client = _mock_client("UNCHANGED")

    with patch("app.chat.contextualization.genai.Client", return_value=client):
        query = await contextualize_query("What about Zepto?", messages)

    assert "Zepto Kiranakart" in query
    assert "Eternal Blinkit" in query
    assert "Swiggy Instamart" in query
    assert "store expansion" in query
    assert "contribution margin" in query


@pytest.mark.anyio
@pytest.mark.parametrize(
    "failure",
    [
        TimeoutError(),
        errors.ClientError(code=429, response_json={"error": {"message": "limited"}}),
    ],
)
async def test_timeout_and_rate_limit_fall_back_to_structural_inheritance(
    failure: Exception,
) -> None:
    messages = [
        _message(
            "user",
            "Compare Blinkit and Swiggy dark-store expansion and gross margins",
        ),
        _message("assistant", "The cited comparison includes gross margins."),
        _message("user", "Add Zepto to that"),
    ]
    client = _mock_client(failure=failure)

    with patch("app.chat.contextualization.genai.Client", return_value=client):
        query = await contextualize_query("Add Zepto to that", messages)

    assert "Zepto Kiranakart" in query
    assert "Eternal Blinkit" in query
    assert "Swiggy Instamart" in query
    assert "store expansion" in query
    assert "gross margin" in query


@pytest.mark.anyio
async def test_self_contained_followup_keeps_its_requested_metrics() -> None:
    messages = [
        _message("user", "Compare Blinkit and Swiggy contribution margins"),
        _message("assistant", "The prior result discussed contribution margin."),
        _message("user", "Compare Zepto revenue and AOV in FY26"),
    ]
    client = _mock_client()
    with patch(
        "app.chat.contextualization.genai.Client",
        return_value=client,
    ) as factory:
        query = await contextualize_query(
            "Compare Zepto revenue and AOV in FY26",
            messages,
        )
    assert query == "Compare Zepto revenue and AOV in FY26"
    factory.assert_not_called()


@pytest.mark.anyio
async def test_standalone_comparison_routes_all_companies_to_parallel_searches() -> (
    None
):
    query = (
        "Compare Eternal Blinkit and Swiggy Instamart with Zepto Kiranakart UDRHP "
        "for dark-store expansion and contribution margin"
    )
    retriever = MagicMock()
    retriever.search = AsyncMock(return_value=[])

    assert detect_companies(query) == ["ETERNAL", "SWIGGY", "ZEPTO"]
    await _retrieve_passages(query, retriever)

    assert retriever.search.await_count == 6
    queries = [call.args[0] for call in retriever.search.call_args_list]
    assert any("Zepto Kiranakart UDRHP" in search_query for search_query in queries)
    assert {
        call.kwargs["filters"].ticker for call in retriever.search.call_args_list
    } == {
        "ETERNAL",
        "SWIGGY",
        "ZEPTO",
    }
    assert len(
        {call.kwargs["embedding_query"] for call in retriever.search.call_args_list}
    ) == 2
