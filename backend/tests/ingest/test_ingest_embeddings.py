from unittest.mock import MagicMock, patch

from ingest.embeddings import embed_texts


@patch("ingest.embeddings.generate_embeddings")
def test_embed_texts_uses_document_task_and_batches(
    mock_generate_embeddings: MagicMock,
) -> None:
    mock_generate_embeddings.side_effect = lambda texts, **_: [
        [float(index)] * 1536 for index, _ in enumerate(texts)
    ]

    result = embed_texts(["first", "second", "third"], batch_size=2)

    assert len(result) == 3
    assert [call.args[0] for call in mock_generate_embeddings.call_args_list] == [
        ["first", "second"],
        ["third"],
    ]
    assert all(
        call.kwargs == {"task_type": "RETRIEVAL_DOCUMENT"}
        for call in mock_generate_embeddings.call_args_list
    )
