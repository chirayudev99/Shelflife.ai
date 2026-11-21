"""Postgres owns tokenization, stemming, and stopword handling for FTS."""


def prepare_fts_query(query: str) -> str:
    return query.strip()
