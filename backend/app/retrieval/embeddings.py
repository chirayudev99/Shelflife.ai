"""Gemini query embedding for live retrieval."""

from __future__ import annotations

from google import genai

from app.embeddings import generate_embeddings


def embed_query(text: str, *, client: genai.Client | None = None) -> list[float]:
    if client is None:
        vectors = generate_embeddings([text], task_type="RETRIEVAL_QUERY")
    else:
        vectors = generate_embeddings(
            [text],
            task_type="RETRIEVAL_QUERY",
            client=client,
        )
    return vectors[0]
