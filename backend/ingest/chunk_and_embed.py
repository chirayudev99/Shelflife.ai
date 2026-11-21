"""Chunk report PDFs, embed chunks, and store them in document_chunks."""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database.models import (
    DocumentChunk,
    DocumentTable,
    MessageCitation,
    SourceDocument,
)
from ingest.chunking import (
    CHUNK_MAX_TOKENS,
    chunk_document,
    document_path_for_accession,
    iter_all_document_paths,
)
from ingest.embeddings import (
    EMBED_BATCH_DELAY_SECONDS,
    EMBED_BATCH_SIZE,
    embed_texts,
)


@dataclass(frozen=True, slots=True)
class IngestCounts:
    processed: int = 0
    skipped: int = 0
    chunks_written: int = 0


def _filing_metadata(document: SourceDocument) -> dict:
    return {
        "ticker": document.ticker,
        "cik": document.cik,
        "company_name": document.company_name,
        "form": document.form,
        "filing_date": document.filing_date.isoformat(),
        "filing_date_basis": document.filing_date_basis,
        "report_date": document.report_date.isoformat()
        if document.report_date
        else None,
        "fiscal_year": document.fiscal_year,
        "accession_number": document.accession_number,
        "primary_document": document.primary_document,
        "source_url": document.source_url,
    }


def _existing_chunk_indexes(session: Session, document_id) -> set[int]:
    return set(
        session.scalars(
            select(DocumentChunk.chunk_index).where(
                DocumentChunk.document_id == document_id
            )
        )
    )


def _delete_chunks(session: Session, document_id) -> None:
    chunk_ids = select(DocumentChunk.id).where(DocumentChunk.document_id == document_id)
    session.execute(
        delete(MessageCitation).where(MessageCitation.chunk_id.in_(chunk_ids))
    )
    session.execute(
        delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
    )
    session.execute(
        delete(DocumentTable).where(DocumentTable.document_id == document_id)
    )


def ingest_document(
    session: Session,
    document: SourceDocument,
    *,
    max_chunks: int | None = None,
    dry_run: bool = False,
    skip_existing: bool = True,
    force: bool = False,
) -> int:
    if force and not dry_run:
        _delete_chunks(session, document.id)
    source_path = document_path_for_accession(document.accession_number)
    print(f"Chunking {document.accession_number} from {source_path.name}...")
    records = chunk_document(
        source_path,
        _filing_metadata(document),
        max_chunks=max_chunks,
    )

    if skip_existing and not force:
        existing_indexes = _existing_chunk_indexes(session, document.id)
        records = [
            record for record in records if record.chunk_index not in existing_indexes
        ]

    if not records:
        print(f"No new chunks to embed for {document.accession_number}")
        return 0

    max_tokens = max(record.token_count for record in records)
    print(
        f"  {len(records)} chunk(s), max_tokens={max_tokens}, limit={CHUNK_MAX_TOKENS}"
    )

    if dry_run:
        sample = records[0]
        print(f"  sample section={sample.section!r} page={sample.page!r}")
        print(f"  sample preview={sample.text[:120]!r}")
        return len(records)

    print(
        f"  Embedding {len(records)} chunk(s) "
        f"(batch_size={EMBED_BATCH_SIZE}, "
        f"pause={EMBED_BATCH_DELAY_SECONDS}s between requests)..."
    )
    for start in range(0, len(records), EMBED_BATCH_SIZE):
        batch = records[start : start + EMBED_BATCH_SIZE]
        vectors = embed_texts([record.text for record in batch])

        for record, embedding in zip(batch, vectors, strict=True):
            session.add(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=record.chunk_index,
                    page=record.page,
                    section=record.section,
                    text=record.text,
                    embedding=embedding,
                    token_count=record.token_count,
                    chunk_metadata=record.chunk_metadata,
                )
            )
        session.commit()
        print(f"  Saved {min(start + len(batch), len(records))}/{len(records)} chunks")

    return len(records)


def ingest_accessions(
    accessions: list[str],
    *,
    max_chunks: int | None = None,
    dry_run: bool = False,
    skip_existing: bool = True,
    force: bool = False,
) -> IngestCounts:
    engine = create_engine(settings.sqlalchemy_database_url)
    counts = IngestCounts()

    with Session(engine) as session:
        for accession in accessions:
            document = session.scalar(
                select(SourceDocument).where(
                    SourceDocument.accession_number == accession
                )
            )
            if document is None:
                raise ValueError(
                    f"No source_document for accession {accession}. "
                    "Run `uv run python -m ingest.load_source_documents` first."
                )

            written = ingest_document(
                session,
                document,
                max_chunks=max_chunks,
                dry_run=dry_run,
                skip_existing=skip_existing,
                force=force,
            )
            counts = IngestCounts(
                processed=counts.processed + 1,
                skipped=counts.skipped,
                chunks_written=counts.chunks_written + written,
            )

    return counts


def ingest_all(
    *,
    max_chunks: int | None = None,
    dry_run: bool = False,
    skip_existing: bool = True,
    force: bool = False,
) -> IngestCounts:
    accessions = [accession for accession, _ in iter_all_document_paths()]
    return ingest_accessions(
        accessions,
        max_chunks=max_chunks,
        dry_run=dry_run,
        skip_existing=skip_existing,
        force=force,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--accession", help="Process one report by accession number")
    target.add_argument(
        "--all", action="store_true", help="Process all manifest reports"
    )
    parser.add_argument(
        "--max-chunks",
        type=int,
        default=None,
        help="Cap chunks per document (use 1 for smoke test)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chunk only; no embeddings or database writes",
    )
    parser.add_argument(
        "--skip-existing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip documents that already have chunks (default: true)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete existing chunks for target document(s) before re-ingesting",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.all:
        result = ingest_all(
            max_chunks=args.max_chunks,
            dry_run=args.dry_run,
            skip_existing=args.skip_existing,
            force=args.force,
        )
    else:
        result = ingest_accessions(
            [args.accession],
            max_chunks=args.max_chunks,
            dry_run=args.dry_run,
            skip_existing=args.skip_existing,
            force=args.force,
        )

    print(
        "Done: "
        f"{result.processed} document(s) processed, "
        f"{result.skipped} skipped, "
        f"{result.chunks_written} chunk(s) written"
    )


if __name__ == "__main__":
    main()
