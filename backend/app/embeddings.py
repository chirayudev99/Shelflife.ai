"""Shared Gemini embedding generation for indexing and retrieval."""

from __future__ import annotations

import logging
import re
from math import fsum, isfinite, sqrt
from time import sleep

from google import genai
from google.genai import errors
from google.genai import types

from app.config import settings

logger = logging.getLogger(__name__)
_MAX_RATE_LIMIT_RETRIES = 4
_RETRY_DELAY_RE = re.compile(r"retry in ([\d.]+)s", re.IGNORECASE)


def _retry_delay_seconds(error: errors.ClientError, attempt: int) -> float:
    message = error.message or ""
    match = _RETRY_DELAY_RE.search(message)
    if match:
        return float(match.group(1))
    return min(2**attempt, 30)


def generate_embeddings(
    texts: list[str],
    *,
    task_type: str,
    client: genai.Client | None = None,
) -> list[list[float]]:
    if not texts:
        return []

    owns_client = client is None
    resolved_client = client or genai.Client(api_key=settings.google_api_key)
    try:
        for attempt in range(_MAX_RATE_LIMIT_RETRIES + 1):
            try:
                response = resolved_client.models.embed_content(
                    model=settings.gemini_embedding_model,
                    contents=texts,
                    config=types.EmbedContentConfig(
                        task_type=task_type,
                        output_dimensionality=settings.embedding_dimensions,
                        http_options=types.HttpOptions(
                            retry_options=types.HttpRetryOptions(attempts=1)
                        ),
                    ),
                )
                break
            except errors.ClientError as error:
                message = (error.message or "").lower()
                if error.code != 429 or "per day limit exceeded" in message:
                    raise
                if attempt == _MAX_RATE_LIMIT_RETRIES:
                    raise
                delay = _retry_delay_seconds(error, attempt)
                logger.warning(
                    "Gemini embedding rate limit hit; retrying in %.1f seconds",
                    delay,
                )
                sleep(delay)

        embeddings = response.embeddings
        if embeddings is None or len(embeddings) != len(texts):
            raise ValueError(
                f"Expected {len(texts)} embeddings, got {len(embeddings or [])}"
            )

        vectors: list[list[float]] = []
        for embedding in embeddings:
            values = embedding.values
            if values is None or len(values) != settings.embedding_dimensions:
                actual_dimensions = len(values) if values is not None else 0
                raise ValueError(
                    f"Expected embedding dimension {settings.embedding_dimensions}, "
                    f"got {actual_dimensions}"
                )
            if not all(isfinite(value) for value in values):
                raise ValueError("Embedding values must be finite.")

            norm = sqrt(fsum(value * value for value in values))
            if norm == 0:
                raise ValueError("Embedding vector must have a non-zero norm.")
            vectors.append([value / norm for value in values])

        return vectors
    finally:
        if owns_client:
            resolved_client.close()
