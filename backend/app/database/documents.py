"""Chunk and source-document lookups for retrieval and agent tools."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database.models import DocumentChunk, SourceDocument


async def get_chunks_by_ids(
    session: AsyncSession,
    chunk_ids: list[UUID],
) -> dict[UUID, DocumentChunk]:
    if not chunk_ids:
        return {}

    rows = (
        await session.scalars(
            select(DocumentChunk)
            .options(joinedload(DocumentChunk.document))
            .where(DocumentChunk.id.in_(chunk_ids))
        )
    ).all()
    return {row.id: row for row in rows}


async def get_chunk_with_document(
    session: AsyncSession,
    chunk_id: UUID,
) -> tuple[DocumentChunk, SourceDocument] | None:
    chunk = await session.scalar(
        select(DocumentChunk)
        .options(joinedload(DocumentChunk.document))
        .where(DocumentChunk.id == chunk_id)
    )
    if chunk is None or chunk.document is None:
        return None
    return chunk, chunk.document


async def get_surrounding_chunks(
    session: AsyncSession,
    anchors: list[DocumentChunk],
    radius: int,
) -> dict[UUID, list[DocumentChunk]]:
    neighbors_by_anchor = {anchor.id: [] for anchor in anchors}
    if radius < 1 or not anchors:
        return neighbors_by_anchor

    ranges = [
        and_(
            DocumentChunk.document_id == anchor.document_id,
            DocumentChunk.chunk_index >= anchor.chunk_index - radius,
            DocumentChunk.chunk_index <= anchor.chunk_index + radius,
        )
        for anchor in anchors
    ]
    result = await session.scalars(
        select(DocumentChunk)
        .options(joinedload(DocumentChunk.document))
        .where(or_(*ranges))
        .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
    )
    rows = result.all()
    chunks_by_position = {
        (chunk.document_id, chunk.chunk_index): chunk for chunk in rows
    }
    for anchor in anchors:
        for chunk_index in range(
            anchor.chunk_index - radius,
            anchor.chunk_index + radius + 1,
        ):
            neighbor = chunks_by_position.get((anchor.document_id, chunk_index))
            if neighbor is not None and neighbor.id != anchor.id:
                neighbors_by_anchor[anchor.id].append(neighbor)
    return neighbors_by_anchor


async def get_chunk_context(
    session: AsyncSession,
    chunk_id: UUID,
    radius: int,
) -> list[DocumentChunk] | None:
    anchor = await session.scalar(
        select(DocumentChunk)
        .options(joinedload(DocumentChunk.document))
        .where(DocumentChunk.id == chunk_id)
    )
    if anchor is None:
        return None

    min_index = anchor.chunk_index - radius
    max_index = anchor.chunk_index + radius
    result = await session.scalars(
        select(DocumentChunk)
        .options(joinedload(DocumentChunk.document))
        .where(
            DocumentChunk.document_id == anchor.document_id,
            DocumentChunk.chunk_index >= min_index,
            DocumentChunk.chunk_index <= max_index,
        )
        .order_by(DocumentChunk.chunk_index)
    )
    return list(result.all())
