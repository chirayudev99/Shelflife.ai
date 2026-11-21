from __future__ import annotations

import pytest
from google import genai

from app.config import settings
from app.database.session import create_async_session_resources
from app.retrieval.retriever import DocumentRetriever
from app.retrieval.types import SearchFilters, format_passages_for_agent

pytestmark = pytest.mark.integration


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("query", "ticker"),
    [
        ("Blinkit dark-store count and contribution margin", "ETERNAL"),
        ("Swiggy Instamart GOV and AOV", "SWIGGY"),
    ],
)
async def test_retriever_returns_company_filtered_passages(
    query: str,
    ticker: str,
) -> None:
    client = genai.Client(api_key=settings.google_api_key)
    engine, session_factory = create_async_session_resources(
        settings.sqlalchemy_database_url
    )
    try:
        retriever = DocumentRetriever(
            session_factory=session_factory,
            google_client=client,
        )
        passages = await retriever.search(
            query,
            filters=SearchFilters(ticker=ticker),
            top_k=5,
        )

        assert passages, f"No passages returned for query: {query!r}"
        assert all(passage.ticker == ticker for passage in passages)
        assert ticker in format_passages_for_agent(passages)
    finally:
        await engine.dispose()
        client.close()
        await client.aio.aclose()
