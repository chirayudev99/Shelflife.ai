"""Token-bounded chunking for Indian quick-commerce report Markdown."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tiktoken

CHUNK_MAX_TOKENS = 512
MARKDOWN_DIR = Path(__file__).resolve().parents[2] / "data" / "markdown"
MANIFEST_PATH = MARKDOWN_DIR / "manifest.json"

_SECTION_HEADING_RE = re.compile(
    r"\b(?:(?:chapter|part|section|schedule|annexure|appendix)\s+"
    r"(?:[A-Z]|\d+(?:\.\d+)*)|"
    r"risk factors|financial statements|business overview|"
    r"management discussion and analysis|corporate governance)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ChunkRecord:
    chunk_index: int
    text: str
    page: str | None
    section: str | None
    token_count: int
    chunk_metadata: dict[str, Any]


def load_manifest_document_paths() -> dict[str, str]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    paths: dict[str, str] = {}
    for filing in manifest.get("filings", []):
        paths[filing["accession_number"]] = filing.get(
            "markdown_local_path",
            filing["local_path"],
        )
    return paths


def document_path_for_accession(accession_number: str) -> Path:
    paths = load_manifest_document_paths()
    if accession_number not in paths:
        raise KeyError(f"Document {accession_number} not found in {MANIFEST_PATH}")
    document_path = MARKDOWN_DIR / paths[accession_number]
    if not document_path.is_file():
        raise FileNotFoundError(f"Missing Markdown file: {document_path}")
    return document_path


def _section_from_chunk(text: str, current_section: str | None) -> str | None:
    match = _SECTION_HEADING_RE.search(text)
    return match.group(0) if match else current_section


def _token_count(text: str, encoding: Any) -> int:
    return len(
        encoding.encode(
            text,
            allowed_special=set(),
            disallowed_special=(),
        )
    )


def _is_table_chunk(text: str) -> bool:
    return any(line.lstrip().startswith("|") for line in text.splitlines())


def chunk_document(
    source_path: Path,
    filing_metadata: dict[str, Any],
    *,
    max_chunks: int | None = None,
) -> list[ChunkRecord]:
    markdown = source_path.read_text(encoding="utf-8")
    encoding = tiktoken.get_encoding("cl100k_base")
    records: list[ChunkRecord] = []
    current_lines: list[str] = []
    current_section: str | None = None

    def append_record(text: str, section: str | None) -> None:
        clean_text = text.strip()
        if not clean_text:
            return
        token_count = _token_count(clean_text, encoding)
        if token_count > CHUNK_MAX_TOKENS:
            tokens = encoding.encode(
                clean_text,
                allowed_special=set(),
                disallowed_special=(),
            )
            midpoint = len(tokens) // 2
            append_record(encoding.decode(tokens[:midpoint]), section)
            append_record(encoding.decode(tokens[midpoint:]), section)
            return
        records.append(
            ChunkRecord(
                chunk_index=len(records),
                text=clean_text,
                page=None,
                section=section,
                token_count=token_count,
                chunk_metadata={
                    **_base_chunk_metadata(filing_metadata),
                    "chunk_kind": (
                        "table" if _is_table_chunk(clean_text) else "narrative"
                    ),
                    "raw_text": clean_text,
                    "source_format": "markdown",
                },
            )
        )

    def flush_current() -> None:
        if current_lines:
            append_record("\n".join(current_lines), current_section)
            current_lines.clear()

    for line in markdown.splitlines():
        stripped_line = line.strip()
        if not stripped_line:
            continue

        if re.match(r"^#{1,6}\s+", stripped_line):
            flush_current()
            current_section = stripped_line.lstrip("#").strip()
        else:
            section_match = _SECTION_HEADING_RE.search(stripped_line)
            if section_match:
                current_section = section_match.group(0)

        line_tokens = encoding.encode(
            line,
            allowed_special=set(),
            disallowed_special=(),
        )
        if len(line_tokens) > CHUNK_MAX_TOKENS:
            flush_current()
            for offset in range(0, len(line_tokens), CHUNK_MAX_TOKENS):
                piece = encoding.decode(line_tokens[offset : offset + CHUNK_MAX_TOKENS])
                append_record(piece, _section_from_chunk(piece, current_section))
            continue

        candidate = "\n".join([*current_lines, line])
        if current_lines and _token_count(candidate, encoding) > CHUNK_MAX_TOKENS:
            flush_current()
        current_lines.append(line)

    flush_current()
    if max_chunks is not None:
        return records[:max_chunks]
    return records


def _base_chunk_metadata(filing_metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": filing_metadata.get("ticker"),
        "cik": filing_metadata.get("cik"),
        "company_name": filing_metadata.get("company_name"),
        "form": filing_metadata.get("form"),
        "filing_date": filing_metadata.get("filing_date"),
        "filing_date_basis": filing_metadata.get("filing_date_basis"),
        "report_date": filing_metadata.get("report_date"),
        "fiscal_year": filing_metadata.get("fiscal_year"),
        "accession_number": filing_metadata.get("accession_number"),
        "primary_document": filing_metadata.get("primary_document"),
        "source_url": filing_metadata.get("source_url"),
    }


def iter_all_document_paths() -> Iterator[tuple[str, Path]]:
    for accession, relative_path in load_manifest_document_paths().items():
        yield accession, MARKDOWN_DIR / relative_path
