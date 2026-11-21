# /// script
# requires-python = ">=3.12"
# dependencies = ["pymupdf4llm"]
# ///
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pymupdf4llm

INPUT_DIR = Path(__file__).resolve().parent / "downloads"
OUTPUT_DIR = Path(__file__).resolve().parent / "markdown"


def convert_downloads_to_markdown() -> dict:
    manifest_path = INPUT_DIR / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"Missing {manifest_path}. Run `uv run data/build_manifest.py` first."
        )

    source_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    filings = source_manifest.get("filings", [])
    if not filings:
        raise ValueError(f"No documents listed in {manifest_path}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest = {
        "source": source_manifest["source"],
        "converted_at_utc": datetime.now(UTC).isoformat(),
        "converted_count": 0,
        "skipped_count": 0,
        "filing_date_note": source_manifest.get("filing_date_note"),
        "filings": [],
    }

    for filing in filings:
        pdf_relative = filing["local_path"]
        pdf_path = INPUT_DIR / pdf_relative
        if pdf_path.suffix.lower() != ".pdf":
            raise ValueError(f"Expected a PDF source, got: {pdf_path}")
        if not pdf_path.is_file():
            raise FileNotFoundError(f"Missing PDF file: {pdf_path}")

        md_relative = Path(pdf_relative).with_suffix(".md").as_posix()
        md_path = OUTPUT_DIR / md_relative
        md_path.parent.mkdir(parents=True, exist_ok=True)
        if md_path.is_file() and md_path.stat().st_size > 0:
            print(f"Keeping existing Markdown {md_relative}")
            manifest["filings"].append(
                {
                    **filing,
                    "pdf_local_path": pdf_relative,
                    "markdown_local_path": md_relative,
                    "local_path": md_relative,
                }
            )
            manifest["skipped_count"] += 1
            continue

        print(f"Converting {pdf_relative}...")
        md_path.write_text(
            pymupdf4llm.to_markdown(pdf_path),
            encoding="utf-8",
        )

        manifest_filing = {
            **filing,
            "pdf_local_path": pdf_relative,
            "markdown_local_path": md_relative,
            "local_path": md_relative,
        }
        manifest["filings"].append(manifest_filing)
        manifest["converted_count"] += 1

    output_manifest_path = OUTPUT_DIR / "manifest.json"
    output_manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


if __name__ == "__main__":
    result = convert_downloads_to_markdown()
    print(
        f"Converted {result['converted_count']} document(s) from {INPUT_DIR} to {OUTPUT_DIR}"
    )
    print(f"Manifest: {OUTPUT_DIR / 'manifest.json'}")
