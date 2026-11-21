"""Hybrid retrieval orchestrator: embed → search → fuse → hydrate."""

from __future__ import annotations

import asyncio
from uuid import UUID

from google import genai
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.database.documents import get_chunks_by_ids, get_surrounding_chunks
from app.database.models import DocumentChunk, SourceDocument
from app.retrieval.embeddings import embed_query
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.keywords import prepare_fts_query
from app.retrieval.queries import full_text_search, semantic_search
from app.retrieval.types import RetrievedPassage, SearchFilters


class DocumentRetriever:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        google_client: genai.Client | None = None,
    ) -> None:
        self.session_factory = session_factory
        self._google_client = google_client
        self._embedding_tasks: dict[str, asyncio.Task[list[float]]] = {}

    async def _embedding_for(self, query: str) -> list[float]:
        task = self._embedding_tasks.get(query)
        if task is None:
            task = asyncio.create_task(
                asyncio.to_thread(
                    embed_query,
                    query,
                    client=self._google_client,
                )
            )
            self._embedding_tasks[query] = task
            task.add_done_callback(
                lambda completed: self._forget_failed_embedding(query, completed)
            )
        return await asyncio.shield(task)

    def _forget_failed_embedding(
        self,
        query: str,
        task: asyncio.Task[list[float]],
    ) -> None:
        if task.cancelled() or task.exception() is not None:
            if self._embedding_tasks.get(query) is task:
                del self._embedding_tasks[query]

    async def search(
        self,
        query: str,
        *,
        filters: SearchFilters | None = None,
        top_k: int | None = None,
        candidate_k: int | None = None,
        include_neighbors: bool = True,
        session: AsyncSession | None = None,
        embedding_query: str | None = None,
    ) -> list[RetrievedPassage]:
        session_factory = self.session_factory
        resolved_top_k = top_k if top_k is not None else settings.retrieval_top_k
        resolved_candidate_k = (
            candidate_k if candidate_k is not None else settings.retrieval_candidate_k
        )
        if session is None and session_factory is None:
            raise RuntimeError("DocumentRetriever requires an async session factory.")
        query_vec = await self._embedding_for(embedding_query or query)
        if session is not None:
            return await self._search_with_session(
                session,
                query_vec,
                query,
                filters=filters,
                top_k=resolved_top_k,
                candidate_k=resolved_candidate_k,
                include_neighbors=include_neighbors,
            )

        async with session_factory() as owned_session:
            async with owned_session.begin():
                return await self._search_with_session(
                    owned_session,
                    query_vec,
                    query,
                    filters=filters,
                    top_k=resolved_top_k,
                    candidate_k=resolved_candidate_k,
                    include_neighbors=include_neighbors,
                )

    async def _search_with_session(
        self,
        session: AsyncSession,
        query_vec: list[float],
        query: str,
        *,
        filters: SearchFilters | None,
        top_k: int,
        candidate_k: int,
        include_neighbors: bool,
    ) -> list[RetrievedPassage]:
        semantic_hits = await semantic_search(
            session,
            query_vec,
            limit=candidate_k,
            filters=filters,
        )
        fts_hits = await full_text_search(
            session,
            prepare_fts_query(query),
            limit=candidate_k,
            filters=filters,
        )

        fused = reciprocal_rank_fusion(
            [
                [hit.chunk_id for hit in semantic_hits],
                [hit.chunk_id for hit in fts_hits],
            ],
            k=settings.retrieval_rrf_k,
        )[:top_k]
        if not fused:
            return []

        fused_ids = [chunk_id for chunk_id, _ in fused]
        fusion_scores = {chunk_id: score for chunk_id, score in fused}
        chunks_by_id = await get_chunks_by_ids(session, fused_ids)
        anchors = [
            chunks_by_id[chunk_id]
            for chunk_id in fused_ids
            if chunk_id in chunks_by_id and chunks_by_id[chunk_id].document is not None
        ]
        neighbors_by_anchor = (
            await get_surrounding_chunks(
                session,
                anchors,
                settings.retrieval_neighbor_radius,
            )
            if include_neighbors
            else {}
        )

        passages: list[RetrievedPassage] = []
        seen_neighbor_ids: set[UUID] = set(fused_ids)
        for chunk_id in fused_ids:
            chunk = chunks_by_id.get(chunk_id)
            if chunk is None or chunk.document is None:
                continue
            neighbors = []
            for neighbor in neighbors_by_anchor.get(chunk_id, []):
                if neighbor.id in seen_neighbor_ids or neighbor.document is None:
                    continue
                seen_neighbor_ids.add(neighbor.id)
                neighbors.append(
                    _passage_from_chunk(
                        neighbor,
                        neighbor.document,
                        fusion_score=0.0,
                    )
                )
            passages.append(
                _passage_from_chunk(
                    chunk,
                    chunk.document,
                    fusion_score=fusion_scores[chunk_id],
                    neighbors=neighbors,
                )
            )
        return passages


def _passage_from_chunk(
    chunk: DocumentChunk,
    document: SourceDocument,
    *,
    fusion_score: float,
    neighbors: list[RetrievedPassage] | None = None,
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
        neighbors=neighbors or [],
        document_title=document.primary_document,
    )
