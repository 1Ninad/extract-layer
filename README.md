# LiteParse + Docling PDF-to-Markdown Pipeline

This repository uses LiteParse for the document text and Docling's accurate
TableFormer extraction only for tables. The merged Markdown is written under
`output/markdown/<pdf-stem>/` and is the input to the Excel mapper.

## Setup

Use Python 3.12 on macOS for the broadest wheel compatibility:

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

## Run

```bash
source .venv/bin/activate
python scripts/run_all.py
```

For each PDF, outputs are:

- `output/markdown/<pdf-stem>/liteparse.md` — LiteParse's document text
- `output/markdown/<pdf-stem>/docling_tables.md` — Docling table output only
- `output/markdown/<pdf-stem>/docling_tables.json` — table data and page provenance
- `output/markdown/<pdf-stem>/hybrid.md` — LiteParse text plus Docling tables

## Markdown to fixed-schema Excel

The Markdown-to-Excel stage sends `hybrid.md` to an OpenRouter model using
strict JSON-schema output. The model classifies source spans into the fixed
columns; it does not calculate or normalize values. The script rejects any
non-empty mapped value that is not an exact substring of the Markdown. `FileName`
is filled by the script itself.

The output is row-oriented: a certificate with multiple characteristic results
produces one Excel row per result, repeating document-level fields on each row.
All cells are written as text and the workbook has no added styling.

Set `OPENROUTER_API_KEY` (the script also reads `.env`) and run:

```bash
source .venv/bin/activate
python scripts/markdown_to_excel.py \
  output/markdown/ineos/hybrid.md \
  --output output/excel/ineos.xlsx \
  --file-name ineos.pdf \
  --node /Users/ninadkale/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node \
  --node-modules /Users/ninadkale/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules
```

Use `OPENROUTER_MODEL` or `--model` to select a model that supports OpenRouter
structured outputs. `--mapping-json` can save the validated intermediate JSON
for audit/debugging. The default is `mistralai/mistral-small-24b-instruct-2501`, which supports this
script's text input, strict `json_schema` response format, and exact-string
mapping workflow.

## One-command end-to-end run

Place one or more PDFs in `input_pdf/` and run:

```bash
source .venv/bin/activate
python scripts/run_pdf_to_excel.py
```

This runs LiteParse and table-only Docling extraction for every PDF, sends each
`hybrid.md` to OpenRouter, and writes one combined workbook to
`output/excel/all_certificates.xlsx`. Use
`--input-dir /path/to/pdf-folder` for another folder, `--ocr` for scanned PDFs,
`--excel-output /path/to/result.xlsx`, `--liteparse /path/to/lit` to select the
LiteParse executable, and `--model` to override the OpenRouter model.

## Quality settings used

Docling uses accurate TableFormer table extraction, OCR off by default for
text-native PDFs, and cell matching disabled to reduce merged-cell errors.
LiteParse is invoked as `lit parse ... --format markdown --no-ocr`, matching the
known-good command. Add `--ocr` for scanned PDFs.

## Downstream schema extraction

For Excel-oriented field extraction, Markdown is useful for text and tables, but do not discard the parser's structured sidecar output where available. A practical production flow is:

1. Give the selected LLM `hybrid.md` plus a strict JSON Schema and require an empty string for absent values.
2. Validate types, required fields, units, dates, and min/max constraints in code before writing Excel.
3. Keep the original PDF and Docling version beside every extracted record for auditability.

`docling_tables.json` is the compact table-only, provenance-preserving sidecar.
The legacy `docling_to_md.py` and `clean_docling_output.py` scripts remain
available for comparing older full-Docling artifacts, but the Excel runner does
not use them.
