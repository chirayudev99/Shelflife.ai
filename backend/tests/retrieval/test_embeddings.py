from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.embeddings import generate_embeddings
from app.retrieval.embeddings import embed_query


@patch("app.embeddings.genai.Client")
def test_generate_embeddings_sets_task_dimension_and_normalizes(
    mock_client_class: MagicMock,
) -> None:
    mock_client = mock_client_class.return_value
    mock_client.models.embed_content.return_value.embeddings = [
        SimpleNamespace(values=[3.0, 4.0, 0.0]),
    ]

    with patch("app.embeddings.settings.embedding_dimensions", 3):
        vectors = generate_embeddings(["query"], task_type="RETRIEVAL_QUERY")

    assert vectors == [[0.6, 0.8, 0.0]]
    call = mock_client.models.embed_content.call_args.kwargs
    assert call["config"].task_type == "RETRIEVAL_QUERY"
    assert call["config"].output_dimensionality == 3


@patch("app.embeddings.genai.Client")
def test_generate_embeddings_rejects_wrong_dimensions(
    mock_client_class: MagicMock,
) -> None:
    mock_client_class.return_value.models.embed_content.return_value.embeddings = [
        SimpleNamespace(values=[1.0, 0.0]),
    ]

    with (
        patch("app.embeddings.settings.embedding_dimensions", 3),
        pytest.raises(ValueError, match="Expected embedding dimension 3, got 2"),
    ):
        generate_embeddings(["query"], task_type="RETRIEVAL_QUERY")


@patch("app.retrieval.embeddings.generate_embeddings")
def test_embed_query_uses_retrieval_query_task(
    mock_generate_embeddings: MagicMock,
) -> None:
    mock_generate_embeddings.return_value = [[0.0] * 1536]

    result = embed_query("annual report revenue")

    assert len(result) == 1536
    mock_generate_embeddings.assert_called_once_with(
        ["annual report revenue"],
        task_type="RETRIEVAL_QUERY",
    )
