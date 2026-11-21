"""Run one assistant smoke query. Edit QUERY_KEY, then: uv run python scripts/smoke_assistant.py"""

from __future__ import annotations

import asyncio
import sys
import uuid

from google import genai

from app.assistant.agent import run_document_agent
from app.assistant.deps import DocumentAgentDeps, TurnRegistry
from app.assistant.progress import (
    add_progress_listener,
    clear_progress_listeners,
    elapsed_seconds,
    report_progress,
    reset_progress_clock,
)
from app.config import settings
from app.database.session import create_async_session_resources
from app.grounding.validator import GroundingValidator, prune_unreferenced_citations
from app.retrieval.retriever import DocumentRetriever

QUERIES = {
    "dark-stores": "Compare Blinkit and Swiggy Instamart dark-store expansion and contribution margins.",
    "risk-factors": "What key regulatory and supply-chain risks are disclosed in the latest quick-commerce filings?",
    "aov-trends": "Break down quick-commerce average order value and take-rate trends across FY24–FY25.",
    "evidence-check": "Do the filings establish that rapid dark-store expansion caused contribution margins to improve?",
    "underspecified": "What is the best stock to buy right now?",
}

QUERY_KEY = "dark-stores"


def _print_progress(message: str) -> None:
    print(f"[{elapsed_seconds():7.2f}s] {message}", flush=True)


def setup_progress_logging() -> None:
    clear_progress_listeners()
    reset_progress_clock()
    add_progress_listener(_print_progress)


async def main() -> None:
    setup_progress_logging()

    query = QUERIES[QUERY_KEY]
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

        print(f"Model: {settings.gemini_model}", flush=True)
        print(f"Query ({QUERY_KEY}): {query}\n", flush=True)

        answer = prune_unreferenced_citations(await run_document_agent(query, deps))
        validation = await GroundingValidator().validate(answer, registry)

        report_progress(
            f"grounding validation ok={validation.ok} "
            f"insufficient_evidence={answer.insufficient_evidence} "
            f"citations={len(answer.citations)}"
        )
        if validation.error:
            report_progress(f"grounding validation error: {validation.error}")

        print(f"\ninsufficient_evidence: {answer.insufficient_evidence}", flush=True)
        print(f"validation_ok: {validation.ok}", flush=True)
        if validation.error:
            print(f"validation_error: {validation.error}", flush=True)
        print(f"\n{answer.answer}\n", flush=True)

        for citation in answer.citations:
            passage = registry.passages_by_chunk_id.get(citation.chunk_id)
            meta = (
                f"{passage.ticker} {passage.form} p.{passage.page}" if passage else ""
            )
            print(
                f"[{citation.citation_index}] {meta}\n  {citation.excerpt[:200]}",
                flush=True,
            )
    finally:
        await engine.dispose()
        client.close()
        await client.aio.aclose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr, flush=True)
        raise SystemExit(130)
