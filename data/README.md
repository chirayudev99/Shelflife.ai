# Data

Local data artifacts for development live here.

- `downloads/` holds Indian quick-commerce report PDFs, grouped by fiscal year.
- `markdown/` holds Docling-converted Markdown exports with the same year layout and manifest.
- PDF and Markdown payloads are gitignored; manifests are tracked as corpus metadata.
- Build the manifest for the five expected PDFs with `uv run data/build_manifest.py`.
- Convert PDFs to Markdown with `uv run --python 3.12 data/convert_to_markdown.py`.
