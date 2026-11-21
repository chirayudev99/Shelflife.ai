"""Print top retrieval hits for client-brief-style questions."""

from __future__ import annotations

import asyncio

from google import genai

from app.config import settings
from app.database.session import create_async_session_resources
from app.retrieval.retriever import DocumentRetriever
from app.retrieval.types import SearchFilters, format_passages_for_agent

SMOKE_QUERIES: list[tuple[str, SearchFilters | None]] = [
    (
        "How did Blinkit's dark-store count and coverage change across annual reports?",
        SearchFilters(ticker="ETERNAL", form="Annual Report"),
    ),
    (
        "How did Swiggy describe Instamart's gross order value and contribution margin?",
        SearchFilters(ticker="SWIGGY", form="Annual Report"),
    ),
    (
        "What regulatory and supply-chain risks are disclosed in Zepto's prospectus?",
        SearchFilters(ticker="ZEPTO", form="IPO Prospectus (UDRHP)"),
    ),
]


async def main() -> None:
    client = genai.Client(api_key=settings.google_api_key)
    engine, session_factory = create_async_session_resources(
        settings.sqlalchemy_database_url
    )
    try:
        retriever = DocumentRetriever(
            session_factory=session_factory,
            google_client=client,
        )
        for query, filters in SMOKE_QUERIES:
            print("\n" + "=" * 80)
            print(f"Query: {query}")
            if filters is not None:
                print(f"Filters: {filters.model_dump_json()}")
            passages = await retriever.search(query, filters=filters, top_k=5)
            print(format_passages_for_agent(passages))
    finally:
        await engine.dispose()
        client.close()
        await client.aio.aclose()


if __name__ == "__main__":
    asyncio.run(main())
