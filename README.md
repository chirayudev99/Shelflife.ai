# ShelfLife

An AI-powered financial research copilot for Indian quick-commerce filings. Ask questions in plain English and get source-grounded answers with verifiable citations.

Visit [shelflife.ai](https://shelflife.ai). Product brief: [docs/client-brief.md](docs/client-brief.md)

## Stack

| Layer              | Choice                                               |
| ------------------ | ---------------------------------------------------- |
| Backend            | Python + FastAPI                                     |
| Frontend           | Vite + React SPA + TypeScript                        |
| Database           | Supabase Postgres (users, chats, documents, chunks)  |
| Migrations         | SQLAlchemy models + Alembic                          |
| Retrieval          | Supabase `pgvector` + Postgres full-text search      |
| Auth               | Supabase Auth (email only)                           |
| Hosting            | Railway                                              |
| LLM + embeddings   | Google Gemini                                       |

## Repo layout

```text
document-copilot/
├── AGENTS.md           # agent instructions (read first)
├── README.md           # this file
├── data/               # local corpus + download script (payloads gitignored)
├── docs/
│   └── client-brief.md # the client one-pager
├── backend/            # FastAPI service
└── frontend/           # React SPA (Vite)
```

## Prerequisites

Install these before setting up `backend/` or `frontend/`:

| Tool | Version | Used for | Install |
| ---- | ------- | -------- | ------- |
| [Python](https://www.python.org/downloads/) | 3.12+ | Backend runtime | OS package manager or python.org |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | latest | Backend deps + PDF conversion scripts | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| [Node.js](https://nodejs.org/) | 20+ (LTS) | Frontend toolchain | nodejs.org or `nvm install --lts` |
| [pnpm](https://pnpm.io/installation) | latest | Frontend package manager | `corepack enable && corepack prepare pnpm@latest --activate` |

You also need accounts/keys for external services once the app is wired up. Start with [docs/guides/supabase-setup.md](docs/guides/supabase-setup.md) (account + project), then create a [Google AI Studio API key](https://aistudio.google.com/apikey) for Gemini.

## Running locally

Start with [docs/guides/supabase-setup.md](docs/guides/supabase-setup.md), then create env files for both services.

Backend env:

```bash
cd backend
cp .env.example .env
```

Fill these values in `backend/.env`:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `DATABASE_URL` using the direct Supabase Postgres connection, not the transaction pooler
- `GOOGLE_API_KEY`
- `ALLOWED_ORIGINS=http://localhost:5173`

Frontend env:

```bash
cd frontend
cp .env.example .env
```

Fill these values in `frontend/.env`:

- `VITE_API_BASE_URL=http://localhost:8000`
- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`

Install dependencies and migrate the database:

```bash
cd backend
uv sync
uv run alembic upgrade head

cd ../frontend
pnpm install
```

Run the backend:

```bash
cd backend
uv run uvicorn app.main:app --reload
```

Run the frontend in another terminal:

```bash
cd frontend
pnpm dev
```

Open the Vite URL, usually `http://localhost:5173`.

Useful checks:

```bash
cd backend
uv run pytest -m "not integration"
uv run ruff check .
uv run python scripts/smoke_retrieval.py

cd ../frontend
pnpm lint
pnpm build
```

## Indian quick-commerce corpus

Place the five source PDFs in their year folders under `data/downloads/`, then generate the corpus manifest:

```bash
uv run data/build_manifest.py
```

Convert only missing or empty Markdown outputs; existing non-empty files are preserved:

```bash
uv run data/convert_to_markdown.py
```

Load report metadata into Supabase:

```bash
cd backend
uv sync --extra ingest
uv run python -m ingest.load_source_documents
```

Chunk and embed all reports:

```bash
cd backend
uv run python -m ingest.chunk_and_embed --all
```

Update an existing corpus:

```bash
# Re-run metadata loading; existing rows are skipped by default.
cd backend
uv run python -m ingest.load_source_documents

# Ingest only new filings; existing chunks are skipped by default.
uv run python -m ingest.chunk_and_embed --all
```

Force-refresh chunks for one report after changing chunking logic:

```bash
cd backend
uv run python -m ingest.chunk_and_embed --accession eternal-fy25-ar --force
```
