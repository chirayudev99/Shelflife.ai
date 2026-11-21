"""Bounded agent tools over the retrieval layer."""

from __future__ import annotations

import time
from uuid import UUID

from pydantic_ai import RunContext

from app.assistant.deps import DocumentAgentDeps
from app.assistant.progress import report_progress
from app.assistant.status import emit_tool_start
from app.config import settings
from app.database.documents import (
    get_chunk_with_document,
    get_chunks_by_ids,
    get_surrounding_chunks,
)
from app.database.models import DocumentChunk, SourceDocument
from app.retrieval.types import (
    RetrievedPassage,
    SearchFilters,
    format_passages_for_agent,
)


def _passage_from_chunk(
    chunk: DocumentChunk,
    document: SourceDocument,
    *,
    fusion_score: float = 0.0,
) -> RetrievedPassage:
    return RetrievedPassage(
        chunk_id=chunk.id,
        document_id=chunk.document_id,
        chunk_index=chunk.chunk_index,
        text=chunk.text,
        page=chunk.page,
        section=chunk.section,
        fusion_score=fusion_score,
        ticker=document.ticker,
        company_name=document.company_name,
        form=document.form,
        filing_date=document.filing_date,
        fiscal_year=document.fiscal_year,
        accession_number=document.accession_number,
        document_title=document.primary_document,
        neighbors=[],
    )


def _parse_fiscal_years(raw: str | None) -> list[int] | None:
    if not raw:
        return None
    years = [int(part.strip()) for part in raw.split(",") if part.strip()]
    return years or None


async def _search(
    deps: DocumentAgentDeps,
    query: str,
    *,
    ticker: str | None,
    form: str | None,
    fiscal_years: str | None,
) -> list[RetrievedPassage]:
    filters = SearchFilters(
        ticker=ticker,
        form=form,
        fiscal_years=_parse_fiscal_years(fiscal_years),
    )
    return await deps.retriever.search(query, filters=filters)


async def _read_chunk(
    deps: DocumentAgentDeps, chunk_id: UUID
) -> RetrievedPassage | None:
    if deps.retriever.session_factory is None:
        raise RuntimeError("DocumentRetriever requires an async session factory.")
    async with deps.retriever.session_factory() as session:
        async with session.begin():
            result = await get_chunk_with_document(session, chunk_id)
            if result is None:
                return None
            chunk, document = result
            return _passage_from_chunk(chunk, document)


async def _read_chunks(
    deps: DocumentAgentDeps,
    chunk_ids: list[UUID],
) -> list[RetrievedPassage]:
    if deps.retriever.session_factory is None:
        raise RuntimeError("DocumentRetriever requires an async session factory.")
    async with deps.retriever.session_factory() as session:
        async with session.begin():
            chunks_by_id = await get_chunks_by_ids(session, chunk_ids)
        passages: list[RetrievedPassage] = []
        for chunk_id in chunk_ids:
            chunk = chunks_by_id.get(chunk_id)
            if chunk is None or chunk.document is None:
                continue
            passages.append(_passage_from_chunk(chunk, chunk.document))
        return passages


async def _read_surrounding(
    deps: DocumentAgentDeps,
    chunk_id: UUID,
    radius: int,
) -> list[RetrievedPassage]:
    if deps.retriever.session_factory is None:
        raise RuntimeError("DocumentRetriever requires an async session factory.")
    async with deps.retriever.session_factory() as session:
        async with session.begin():
            anchor = await get_chunk_with_document(session, chunk_id)
            if anchor is None:
                return []
            anchor_chunk, _ = anchor
            neighbor_chunks = await get_surrounding_chunks(
                session,
                [anchor_chunk],
                radius,
            )
        passages: list[RetrievedPassage] = []
        for neighbor_chunk in neighbor_chunks[anchor_chunk.id]:
            if neighbor_chunk.document is None:
                continue
            passages.append(
                _passage_from_chunk(neighbor_chunk, neighbor_chunk.document)
            )
        if anchor_chunk.document is not None:
            passages.insert(
                0,
                _passage_from_chunk(anchor_chunk, anchor_chunk.document),
            )
        return passages


async def _run_tool(
    deps: DocumentAgentDeps,
    name: str,
    detail: str,
    fn,
    /,
    *args,
    **kwargs,
):
    emit_tool_start(deps, name, detail)
    started = time.perf_counter()
    try:
        result = await fn(*args, **kwargs)
    finally:
        elapsed = time.perf_counter() - started
        deps.retrieval_ms += elapsed * 1000
    if isinstance(result, list):
        summary = f"{len(result)} results"
    elif result is None:
        summary = "not found"
    else:
        summary = "1 result"
    report_progress(f"tool {name} done ({summary}) in {elapsed:.2f}s")
    return result


async def search_filings(
    ctx: RunContext[DocumentAgentDeps],
    query: str,
    ticker: str | None = None,
    form: str | None = None,
    fiscal_years: str | None = None,
) -> str:
    """Search Indian quick-commerce filings.

    For comparisons, include all companies in one query and leave ticker unset
    rather than making separate searches for each company.
    """
    filter_bits = [
        bit
        for bit in (
            f"ticker={ticker}" if ticker else None,
            f"form={form}" if form else None,
            f"fiscal_years={fiscal_years}" if fiscal_years else None,
        )
        if bit
    ]
    detail = ", ".join(filter_bits) if filter_bits else "no filters"
    passages = await _run_tool(
        ctx.deps,
        "search_filings",
        detail,
        _search,
        ctx.deps,
        query,
        ticker=ticker,
        form=form,
        fiscal_years=fiscal_years,
    )
    ctx.deps.registry.register_many(passages)
    return format_passages_for_agent(passages)


async def read_chunk(ctx: RunContext[DocumentAgentDeps], chunk_id: str) -> str:
    """Read the full text of a specific document chunk by UUID."""
    try:
        parsed_id = UUID(chunk_id)
    except ValueError:
        return f"Error: invalid chunk_id {chunk_id!r}."

    passage = await _run_tool(
        ctx.deps,
        "read_chunk",
        f"chunk_id={chunk_id}",
        _read_chunk,
        ctx.deps,
        parsed_id,
    )
    if passage is None:
        return f"Error: chunk {chunk_id} not found."

    ctx.deps.registry.register(passage)
    return format_passages_for_agent([passage])


async def read_chunks(ctx: RunContext[DocumentAgentDeps], chunk_ids: list[str]) -> str:
    """Read the full text of multiple document chunks in one call."""
    parsed_ids: list[UUID] = []
    for chunk_id in chunk_ids:
        try:
            parsed_ids.append(UUID(chunk_id))
        except ValueError:
            return f"Error: invalid chunk_id {chunk_id!r}."

    if not parsed_ids:
        return "Error: chunk_ids must include at least one UUID."

    passages = await _run_tool(
        ctx.deps,
        "read_chunks",
        f"count={len(parsed_ids)}",
        _read_chunks,
        ctx.deps,
        parsed_ids,
    )
    if not passages:
        return "Error: none of the requested chunks were found."

    ctx.deps.registry.register_many(passages)
    return format_passages_for_agent(passages)


async def read_surrounding_chunks(
    ctx: RunContext[DocumentAgentDeps],
    chunk_id: str,
    radius: int | None = None,
) -> str:
    """Read chunks before and after a given chunk within the same filing."""
    try:
        parsed_id = UUID(chunk_id)
    except ValueError:
        return f"Error: invalid chunk_id {chunk_id!r}."

    resolved_radius = (
        radius if radius is not None else settings.retrieval_neighbor_radius
    )
    if resolved_radius < 1:
        return "Error: radius must be 1 or greater."

    passages = await _run_tool(
        ctx.deps,
        "read_surrounding_chunks",
        f"chunk_id={chunk_id} radius={resolved_radius}",
        _read_surrounding,
        ctx.deps,
        parsed_id,
        resolved_radius,
    )
    if not passages:
        return f"Error: chunk {chunk_id} not found."

    ctx.deps.registry.register_many(passages)
    return format_passages_for_agent(passages)
