from __future__ import annotations

import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from app.database.models import DocumentChunk, SourceDocument
from app.retrieval.retriever import DocumentRetriever
from app.retrieval.types import RankedChunkHit, SearchFilters

ID_A = UUID("00000000-0000-0000-0000-000000000001")
ID_B = UUID("00000000-0000-0000-0000-000000000002")
ID_N1 = UUID("00000000-0000-0000-0000-000000000011")
DOC_ID = UUID("00000000-0000-0000-0000-000000000100")


def _document() -> SourceDocument:
    return SourceDocument(
        id=DOC_ID,
        ticker="ETERNAL",
        cik=None,
        company_name="Eternal Limited",
        form="Annual Report",
        filing_date=date(2025, 5, 1),
        fiscal_year=2025,
        accession_number="eternal-fy25-ar",
        primary_document="eternal_ar_2025.pdf",
        source_url="https://example.com/eternal",
    )


def _chunk(
    chunk_id: UUID,
    *,
    chunk_index: int,
    text: str,
    document: SourceDocument,
) -> DocumentChunk:
    return DocumentChunk(
        id=chunk_id,
        document_id=document.id,
        chunk_index=chunk_index,
        page="42",
        section="Quick Commerce",
        text=text,
        chunk_metadata={},
        document=document,
    )


@pytest.mark.anyio
async def test_document_retriever_fuses_and_hydrates() -> None:
    semantic = AsyncMock(
        return_value=[
            RankedChunkHit(chunk_id=ID_A, rank=1, score=0.9),
            RankedChunkHit(chunk_id=ID_B, rank=2, score=0.8),
        ]
    )
    full_text = AsyncMock(
        return_value=[
            RankedChunkHit(chunk_id=ID_B, rank=1, score=0.7),
            RankedChunkHit(chunk_id=ID_A, rank=2, score=0.6),
        ]
    )
    document = _document()
    chunk_a = _chunk(ID_A, chunk_index=5, text="Blinkit revenue mix", document=document)
    chunk_b = _chunk(ID_B, chunk_index=8, text="Quick commerce growth", document=document)
    neighbor = _chunk(ID_N1, chunk_index=4, text="Prior context", document=document)
    chunks = AsyncMock(return_value={ID_A: chunk_a, ID_B: chunk_b})
    neighbors = AsyncMock(return_value={ID_A: [neighbor], ID_B: []})

    with (
        patch("app.retrieval.retriever.embed_query", return_value=[0.1] * 3) as embed,
        patch("app.retrieval.retriever.semantic_search", semantic),
        patch("app.retrieval.retriever.full_text_search", full_text),
        patch("app.retrieval.retriever.get_chunks_by_ids", chunks),
        patch("app.retrieval.retriever.get_surrounding_chunks", neighbors),
    ):
        retriever = DocumentRetriever()
        passages = await retriever.search(
            "Eternal Blinkit revenue mix",
            filters=SearchFilters(ticker="ETERNAL"),
            top_k=2,
            candidate_k=50,
            session=MagicMock(),
        )

    assert len(passages) == 2
    assert {passage.chunk_id for passage in passages} == {ID_A, ID_B}
    assert passages[0].fusion_score >= passages[1].fusion_score
    assert passages[0].ticker == "ETERNAL"
    assert passages[0].neighbors[0].chunk_id == ID_N1
    assert passages[0].neighbors[0].fusion_score == 0.0
    embed.assert_called_once_with("Eternal Blinkit revenue mix", client=None)
    assert semantic.await_args.kwargs["filters"] == SearchFilters(ticker="ETERNAL")
    assert semantic.await_args.kwargs["limit"] == 50
    assert full_text.await_args.args[1] == "Eternal Blinkit revenue mix"
    assert neighbors.await_count == 1


@pytest.mark.anyio
async def test_document_retriever_returns_empty_when_no_hits() -> None:
    with (
        patch("app.retrieval.retriever.embed_query", return_value=[0.1] * 3),
        patch("app.retrieval.retriever.semantic_search", AsyncMock(return_value=[])),
        patch("app.retrieval.retriever.full_text_search", AsyncMock(return_value=[])),
        patch("app.retrieval.retriever.get_chunks_by_ids") as get_chunks,
    ):
        retriever = DocumentRetriever()
        passages = await retriever.search("no matching chunks", session=MagicMock())

    assert passages == []
    get_chunks.assert_not_called()


@pytest.mark.anyio
async def test_duplicate_subtopic_queries_share_one_embedding_task() -> None:
    with (
        patch("app.retrieval.retriever.embed_query", return_value=[0.1] * 3) as embed,
        patch("app.retrieval.retriever.semantic_search", AsyncMock(return_value=[])),
        patch("app.retrieval.retriever.full_text_search", AsyncMock(return_value=[])),
    ):
        retriever = DocumentRetriever()
        await asyncio.gather(
            retriever.search(
                "Eternal revenue",
                session=MagicMock(),
                embedding_query="financial metrics",
            ),
            retriever.search(
                "Swiggy revenue",
                session=MagicMock(),
                embedding_query="financial metrics",
            ),
        )

    embed.assert_called_once_with("financial metrics", client=None)
