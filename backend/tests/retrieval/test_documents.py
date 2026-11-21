from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from app.database.documents import get_surrounding_chunks
from app.database.models import DocumentChunk

DOC_A = UUID("00000000-0000-0000-0000-000000000100")
DOC_B = UUID("00000000-0000-0000-0000-000000000200")


def _chunk(document_id: UUID, index: int) -> DocumentChunk:
    return DocumentChunk(
        id=UUID(int=document_id.int + index + 1),
        document_id=document_id,
        chunk_index=index,
        text=f"chunk {index}",
        chunk_metadata={},
    )


@pytest.mark.anyio
async def test_surrounding_chunks_fetches_neighbors_for_all_anchors_once() -> None:
    first_anchor = _chunk(DOC_A, 4)
    second_anchor = _chunk(DOC_B, 8)
    chunks = [
        _chunk(DOC_A, 3),
        first_anchor,
        _chunk(DOC_A, 5),
        _chunk(DOC_B, 7),
        second_anchor,
        _chunk(DOC_B, 9),
    ]
    result = MagicMock()
    result.all.return_value = chunks
    session = MagicMock()
    session.scalars = AsyncMock(return_value=result)

    neighbors = await get_surrounding_chunks(
        session,
        [first_anchor, second_anchor],
        radius=1,
    )

    assert session.scalars.await_count == 1
    assert [chunk.chunk_index for chunk in neighbors[first_anchor.id]] == [3, 5]
    assert [chunk.chunk_index for chunk in neighbors[second_anchor.id]] == [7, 9]
