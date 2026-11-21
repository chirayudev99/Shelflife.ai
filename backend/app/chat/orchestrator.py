"""Coordinates one chat turn: agent → validate → stream → persist."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator

import httpx
from google import genai
from google.genai import errors
from supabase import AsyncClient

from app.assistant.agent import run_document_agent
from app.assistant.deps import DocumentAgentDeps, TurnRegistry
from app.assistant.outputs import GroundedAnswer
from app.auth.dependencies import CurrentUser
from app.chat.contextualization import (
    contextualize_query,
    detect_companies,
    recent_conversation_context,
    should_contextualize_query,
)
from app.chat.messages import text_from_parts
from app.core.companies import COMPANY_REGISTRY
from app.chat.streaming import (
    stream_grounded_turn_and_persist,
    stream_error,
    stream_status,
)
from app.grounding.validator import (
    GroundingValidator,
    map_uuid_markers_to_citations,
    prune_unreferenced_citations,
    retain_retrieved_citations,
    ValidationResult,
)
from app.llm import GeminiFallbackExhausted
from app.retrieval.retriever import DocumentRetriever
from app.retrieval.types import RetrievedPassage, SearchFilters
from app.schemas.chat import UIMessage

logger = logging.getLogger(__name__)

_SUBTOPIC_SEARCHES = {
    "operational": ("dark store count warehousing cities expansion", 3),
    "financial": (
        "quick commerce GOV NOV AOV contribution margin adjusted EBITDA unit economics take rate",
        4,
    ),
}
_MAX_COMPARISON_PASSAGES = 14


def _company_search_terms(ticker: str) -> str:
    return COMPANY_REGISTRY.get(ticker).search_context


def _detect_search_topics(query: str) -> list[str]:
    lowered = query.casefold()
    topics: list[str] = []
    if any(
        term in lowered
        for term in (
            "dark store",
            "dark-store",
            "store count",
            "store expansion",
            "expansion",
            "warehousing",
            "warehouse",
            "cities",
            "city",
            "footprint",
            "fulfillment",
        )
    ):
        topics.append("operational")
    if any(
        term in lowered
        for term in (
            "margin",
            "unit economics",
            "gov",
            "gross order value",
            "nov",
            "net order value",
            "aov",
            "average order value",
            "take rate",
            "ebitda",
            "revenue",
            "profitability",
            "contribution",
            "pat",
            "p&l",
        )
    ):
        topics.append("financial")
    return topics


async def _retrieve_passages(
    query: str,
    retriever: DocumentRetriever,
) -> list[RetrievedPassage]:
    companies = detect_companies(query)
    topics = _detect_search_topics(query)
    if len(companies) >= 2:
        topics = list(_SUBTOPIC_SEARCHES)
    if len(topics) >= 2 or len(companies) >= 2:
        if not topics:
            topics = list(_SUBTOPIC_SEARCHES)
        search_groups = companies or [""]
        search_requests = [
            (
                ticker,
                topic,
                retriever.search(
                    (f"{_company_search_terms(ticker)} " if ticker else "")
                    + f"{_SUBTOPIC_SEARCHES[topic][0]} {query}",
                    filters=SearchFilters(ticker=ticker) if ticker else None,
                    top_k=_SUBTOPIC_SEARCHES[topic][1],
                    include_neighbors=False,
                    embedding_query=f"{_SUBTOPIC_SEARCHES[topic][0]} {query}",
                ),
            )
            for ticker in search_groups
            for topic in topics
        ]
        results = await asyncio.gather(*(request for _, _, request in search_requests))

        passages_by_company: dict[str, dict[str, list[RetrievedPassage]]] = {
            ticker: {} for ticker in search_groups
        }
        for (ticker, topic, _), passages in zip(search_requests, results, strict=True):
            passages_by_company[ticker][topic] = passages

        merged: list[RetrievedPassage] = []
        seen_chunk_ids: set[uuid.UUID] = set()
        max_rank = max(
            (
                len(passages)
                for topic_results in passages_by_company.values()
                for passages in topic_results.values()
            ),
            default=0,
        )
        for rank in range(max_rank):
            for ticker in search_groups:
                for topic in topics:
                    topic_passages = passages_by_company[ticker].get(topic, [])
                    if rank >= len(topic_passages):
                        continue
                    passage = topic_passages[rank]
                    if passage.chunk_id in seen_chunk_ids:
                        continue
                    seen_chunk_ids.add(passage.chunk_id)
                    merged.append(passage)
                    if len(merged) >= _MAX_COMPARISON_PASSAGES:
                        return merged
        return merged

    filters = SearchFilters(ticker=companies[0]) if companies else None
    search_query = (
        f"{_company_search_terms(companies[0])} {query}" if companies else query
    )
    return await retriever.search(
        search_query,
        filters=filters,
        top_k=8,
        include_neighbors=False,
    )


def _log_pipeline_timing(
    *,
    started_at: float,
    retrieval_ms: float,
    generation_ms: float,
    verification_ms: float,
) -> None:
    total_ms = (time.perf_counter() - started_at) * 1000
    logger.info(
        "RAG pipeline timing retrieval_ms=%.1f generation_ms=%.1f "
        "verification_ms=%.1f total_ms=%.1f",
        retrieval_ms,
        generation_ms,
        verification_ms,
        total_ms,
    )


async def _yield_status_updates(
    status_queue: asyncio.Queue[tuple[str, str]],
    agent_task: asyncio.Task[GroundedAnswer],
) -> AsyncIterator[str]:
    while not agent_task.done():
        try:
            stage, message = await asyncio.wait_for(status_queue.get(), timeout=0.3)
        except TimeoutError:
            continue
        async for event in stream_status(stage, message):
            yield event

    while not status_queue.empty():
        stage, message = status_queue.get_nowait()
        async for event in stream_status(stage, message):
            yield event


async def run_turn(
    *,
    client: AsyncClient,
    thread_id: uuid.UUID,
    user: CurrentUser,
    user_message: UIMessage,
    thread_title: str,
    retriever: DocumentRetriever,
    google_client: genai.Client | None = None,
    messages: list[UIMessage] | None = None,
) -> AsyncIterator[str]:
    pipeline_started = time.perf_counter()
    loop = asyncio.get_running_loop()
    query = text_from_parts(user_message.parts).strip()
    if not query:
        async for event in stream_error("User message is empty."):
            yield event
        return

    conversation_messages = messages or [user_message]
    conversation_context = recent_conversation_context(conversation_messages)
    if should_contextualize_query(query, conversation_messages):
        async for event in stream_status(
            "contextualizing",
            "Resolving follow-up context…",
        ):
            yield event
        try:
            query = await contextualize_query(
                query,
                conversation_messages,
                client=google_client,
            )
        except (errors.ClientError, httpx.HTTPError) as exc:
            logger.exception("Follow-up query contextualization failed")
            async for event in stream_error(
                f"Follow-up query contextualization failed: {exc}"
            ):
                yield event
            return

    async for event in stream_status("analyzing", "Analyzing your question…"):
        yield event

    registry = TurnRegistry()
    status_queue = asyncio.Queue()

    def on_status(stage: str, message: str) -> None:
        loop.call_soon_threadsafe(status_queue.put_nowait, (stage, message))

    deps = DocumentAgentDeps(
        retriever=retriever,
        registry=registry,
        thread_id=thread_id,
        user_id=user.id,
        google_client=google_client,
        on_status=on_status,
        conversation_context=conversation_context,
    )

    async for event in stream_status(
        "searching", "Searching relevant company filings…"
    ):
        yield event
    retrieval_started = time.perf_counter()
    try:
        passages = await _retrieve_passages(query, retriever)
    except Exception as exc:
        deps.retrieval_ms += (time.perf_counter() - retrieval_started) * 1000
        _log_pipeline_timing(
            started_at=pipeline_started,
            retrieval_ms=deps.retrieval_ms,
            generation_ms=0.0,
            verification_ms=0.0,
        )
        logger.exception("RAG pre-retrieval failed")
        async for event in stream_error(f"Filing search failed: {exc}"):
            yield event
        return
    deps.retrieval_ms += (time.perf_counter() - retrieval_started) * 1000
    deps.retrieved_passages = passages
    registry.register_many(passages)

    agent_started = time.perf_counter()
    agent_task = asyncio.create_task(run_document_agent(query, deps))

    async for event in _yield_status_updates(status_queue, agent_task):
        yield event

    try:
        grounded = await agent_task
    except GeminiFallbackExhausted as exc:
        _log_pipeline_timing(
            started_at=pipeline_started,
            retrieval_ms=deps.retrieval_ms,
            generation_ms=(time.perf_counter() - agent_started) * 1000,
            verification_ms=0.0,
        )
        logger.warning(
            "Gemini generation fallback exhausted models=%s status=%s",
            ",".join(exc.models),
            exc.status_code,
        )
        error_message = (
            "AI service is experiencing temporary high traffic. "
            "Please retry in a few seconds."
            if exc.status_code == 503
            else "AI service is temporarily rate limited. Please retry in a few seconds."
        )
        async for event in stream_error(error_message):
            yield event
        return
    except Exception as exc:
        _log_pipeline_timing(
            started_at=pipeline_started,
            retrieval_ms=deps.retrieval_ms,
            generation_ms=(time.perf_counter() - agent_started) * 1000,
            verification_ms=0.0,
        )
        logger.exception("RAG agent generation failed")
        async for event in stream_error(f"Assistant run failed: {exc}"):
            yield event
        return

    generation_ms = (time.perf_counter() - agent_started) * 1000
    async for event in stream_status("verifying", "Verifying citations…"):
        yield event

    grounded = map_uuid_markers_to_citations(grounded, registry)
    grounded = prune_unreferenced_citations(grounded)
    verification_started = time.perf_counter()
    validation = await GroundingValidator().validate(grounded, registry)
    verification_ms = (time.perf_counter() - verification_started) * 1000

    if not registry.passages_by_chunk_id:
        logger.info("RAG answer abstained because no source passages were retrieved")
        grounded = GroundedAnswer(
            answer=(
                "I couldn't retrieve relevant source passages from the current "
                "filings, so I can't answer this from the available evidence."
            ),
            citations=[],
            insufficient_evidence=True,
        )
        validation = ValidationResult(ok=True)
    elif grounded.insufficient_evidence:
        grounded = grounded.model_copy(update={"insufficient_evidence": False})
        validation = ValidationResult(
            ok=False,
            error="The agent reported insufficient evidence despite retrieved passages.",
        )

    mentioned_companies = detect_companies(query)
    retrieved_companies = {
        passage.ticker for passage in registry.passages_by_chunk_id.values()
    }
    missing_companies = [
        ticker for ticker in mentioned_companies if ticker not in retrieved_companies
    ]
    if missing_companies and registry.passages_by_chunk_id:
        missing_names = ", ".join(
            COMPANY_REGISTRY.get(ticker).display_name for ticker in missing_companies
        )
        validation = ValidationResult(
            ok=False,
            error=f"No retrieved filing chunks for: {missing_names}.",
            partial=True,
        )

    if not validation.ok:
        logger.warning("RAG answer citation validation failed: %s", validation.error)
        grounded = retain_retrieved_citations(grounded, registry)
        if not grounded.answer.strip():
            grounded = grounded.model_copy(
                update={
                    "answer": (
                        "Relevant filing passages were retrieved, but no complete "
                        "answer could be generated from them."
                    )
                }
            )

    _log_pipeline_timing(
        started_at=pipeline_started,
        retrieval_ms=deps.retrieval_ms,
        generation_ms=generation_ms,
        verification_ms=verification_ms,
    )

    if validation.ok:
        async for event in stream_status("streaming", "Preparing answer…"):
            yield event
    elif validation.partial:
        async for event in stream_status(
            "streaming",
            "Preparing a partially verified answer with source citations…",
        ):
            yield event
    else:
        async for event in stream_status("streaming", "Preparing answer…"):
            yield event

    async for event in stream_grounded_turn_and_persist(
        client=client,
        thread_id=thread_id,
        user_message=user_message,
        thread_title=thread_title,
        answer=grounded,
        registry=registry,
        validation=validation,
    ):
        yield event
