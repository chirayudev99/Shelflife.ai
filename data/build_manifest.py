"""Build the local manifest for the Indian quick-commerce report corpus."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

DOWNLOADS_DIR = Path(__file__).resolve().parent / "downloads"
MANIFEST_PATH = DOWNLOADS_DIR / "manifest.json"

DOCUMENTS = (
    {
        "local_path": "2025/eternal_ar_2025.pdf",
        "ticker": "ETERNAL",
        "company_name": "Eternal Limited (Zomato & Blinkit)",
        "fiscal_year": 2025,
        "form": "Annual Report",
        "accession_number": "eternal-fy25-ar",
    },
    {
        "local_path": "2026/eternal_ar_2026.pdf",
        "ticker": "ETERNAL",
        "company_name": "Eternal Limited (Zomato & Blinkit)",
        "fiscal_year": 2026,
        "form": "Annual Report",
        "accession_number": "eternal-fy26-ar",
    },
    {
        "local_path": "2025/swiggy_ar_2025.pdf",
        "ticker": "SWIGGY",
        "company_name": "Swiggy Limited",
        "fiscal_year": 2025,
        "form": "Annual Report",
        "accession_number": "swiggy-fy25-ar",
    },
    {
        "local_path": "2026/swiggy_ar_2026.pdf",
        "ticker": "SWIGGY",
        "company_name": "Swiggy Limited",
        "fiscal_year": 2026,
        "form": "Annual Report",
        "accession_number": "swiggy-fy26-ar",
    },
    {
        "local_path": "2026/zepto_2026.pdf",
        "ticker": "ZEPTO",
        "company_name": "Zepto Limited",
        "fiscal_year": 2026,
        "form": "IPO Prospectus (UDRHP)",
        "accession_number": "zepto-fy26-udrhp",
    },
)


def build_manifest() -> dict:
    missing = [
        document["local_path"]
        for document in DOCUMENTS
        if not (DOWNLOADS_DIR / document["local_path"]).is_file()
    ]
    if missing:
        raise FileNotFoundError(
            "Missing required PDF(s): " + ", ".join(missing)
        )

    filings = []
    for document in DOCUMENTS:
        report_date = f"{document['fiscal_year']}-03-31"
        filings.append(
            {
                **document,
                "cik": None,
                "filing_date": report_date,
                "filing_date_basis": "fiscal_year_end_proxy",
                "report_date": report_date,
                "primary_document": Path(document["local_path"]).name,
                "source_url": "",
            }
        )

    manifest = {
        "source": "Indian quick-commerce reports",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "filing_date_note": (
            "filing_date uses March 31 of the fiscal year as a reporting-date "
            "proxy, not the actual publication date"
        ),
        "document_count": len(filings),
        "filings": filings,
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


if __name__ == "__main__":
    result = build_manifest()
    print(f"Wrote {result['document_count']} records to {MANIFEST_PATH}")
