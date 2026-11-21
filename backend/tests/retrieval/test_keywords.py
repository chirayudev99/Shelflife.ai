from app.retrieval.keywords import prepare_fts_query


def test_prepare_fts_query_trims_only_outer_whitespace() -> None:
    query = "  Compare Blinkit contribution margins and Swiggy AOV  "

    assert prepare_fts_query(query) == (
        "Compare Blinkit contribution margins and Swiggy AOV"
    )


def test_prepare_fts_query_leaves_postgres_tokenization_terms_intact() -> None:
    query = "What did Eternal disclose about GOV and AOV?"

    assert prepare_fts_query(query) == query
