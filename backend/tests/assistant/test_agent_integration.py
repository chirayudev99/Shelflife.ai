import uuid

import pytest
from google import genai

from app.assistant.agent import run_document_agent
from app.assistant.deps import DocumentAgentDeps, TurnRegistry
from app.config import settings
from app.database.session import create_async_session_resources
from app.grounding.validator import GroundingValidator
from app.retrieval.retriever import DocumentRetriever


async def _run_query(query: str):
    client = genai.Client(api_key=settings.google_api_key)
    engine, session_factory = create_async_session_resources(
        settings.sqlalchemy_database_url
    )
    try:
        retriever = DocumentRetriever(
            session_factory=session_factory,
            google_client=client,
        )
        passages = await retriever.search(query, include_neighbors=False)
        registry = TurnRegistry()
        registry.register_many(passages)
        deps = DocumentAgentDeps(
            retriever=retriever,
            registry=registry,
            thread_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            google_client=client,
            retrieved_passages=passages,
        )
        answer = await run_document_agent(query, deps)
        validation = await GroundingValidator().validate(answer, registry)
        return answer, validation, registry
    finally:
        await engine.dispose()
        client.close()
        await client.aio.aclose()


@pytest.mark.integration
@pytest.mark.anyio
async def test_agent_answers_quick_commerce_filing_question_with_citations() -> None:
    answer, validation, registry = await _run_query(
        "How did Eternal describe Blinkit's quick-commerce revenue?"
    )

    assert validation.ok
    if not answer.insufficient_evidence:
        assert answer.citations
        tickers = {
            registry.passages_by_chunk_id[citation.chunk_id].ticker
            for citation in answer.citations
        }
        assert "ETERNAL" in tickers


@pytest.mark.integration
@pytest.mark.anyio
async def test_agent_refuses_underspecified_stock_pick_question() -> None:
    answer, validation, _ = await _run_query(
        "What is the best stock to buy right now?"
    )

    assert validation.ok
    assert answer.insufficient_evidence or not answer.citations
