"""Gemini embedding generation for document chunks."""

from __future__ import annotations

from time import sleep

from app.embeddings import generate_embeddings

EMBED_BATCH_SIZE = 50
EMBED_BATCH_DELAY_SECONDS = 55


def embed_texts(
    texts: list[str], *, batch_size: int = EMBED_BATCH_SIZE
) -> list[list[float]]:
    if not texts:
        return []

    vectors: list[list[float]] = []

    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        vectors.extend(generate_embeddings(batch, task_type="RETRIEVAL_DOCUMENT"))
        sleep(EMBED_BATCH_DELAY_SECONDS)

    return vectors
