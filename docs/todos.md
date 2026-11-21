# ShelfLife release checklist

## Corpus

- [ ] Confirm the five expected PDFs are present under `data/downloads/`.
- [ ] Run `uv run data/build_manifest.py` and review `data/downloads/manifest.json`.
- [ ] Run `uv run data/convert_to_markdown.py`; confirm each non-empty Markdown file is preserved and missing files are generated.
- [ ] Load source-document metadata and ingest chunks using the backend ingestion commands in the [README](../README.md).
- [ ] Spot-check retrieved passages and page/section citations for each company.

## Local application

- [ ] Configure Supabase and `GOOGLE_API_KEY` in the backend environment.
- [ ] Run `uv sync` and `uv run alembic upgrade head` from `backend/`.
- [ ] Start the FastAPI backend and Vite frontend using the [local setup instructions](../README.md).
- [ ] Verify sign-in, follow-up chat turns, citation links, and conversation history.

## Release readiness

- [ ] Confirm the unauthenticated entry screen fits a desktop and mobile viewport.
- [ ] Review the authenticated workspace, empty state, and citation presentation.
- [ ] Confirm Gemini quotas, database storage, and deployment resource limits for the selected tiers.
- [ ] Review logging and errors for failed retrieval, generation, and ingestion operations.
