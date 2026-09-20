<h1 align="center">Document to Structured Data</h1>

<p align="center">
  <a href="https://www.python.org/">
    <img alt="Python" src="https://img.shields.io/badge/Python-3.12%2B-3776AB?style=flat-square&logo=python&logoColor=white" />
  </a>
  <a href="https://www.linkedin.com/in/ninad22/">
    <img alt="LinkedIn" src="https://img.shields.io/badge/LinkedIn-Ninad%20Kale-0A66C2?style=flat-square&logo=linkedin&logoColor=white" />
  </a>
</p>

<h3 align="center">Turn PDFs into data you can review and use.</h3>

<p align="center">
  <img alt="Document to Structured Data application architecture" src="docs/application-architecture.svg" width="80%" />
</p>

## What it is

PDFs are made for reading. This application makes them easier to use by turning
their text and tables into structured JSON and CSV.

Upload a PDF, choose how you want to extract it, and review the result in the
web workspace. You can let the application find fields automatically or define
the exact fields you need with a schema.

The application is document-agnostic. It does not depend on one fixed PDF
layout, translate values, calculate new values, round numbers, convert units,
or invent missing data. Values are kept as printed in the source document.

Uploads are processed in memory and temporary working directories. They are
not stored by the application.

## Features

- **Two extraction modes** - use deterministic automatic extraction or define a schema for a focused result.
- **PDF-aware parsing** - combine LiteParse text with Docling tables and PDF coordinates.
- **OCR fallback** - retry the complete parsing flow with OCR when native text is not usable.
- **Source-faithful values** - keep spelling, punctuation, symbols, spaces, and numeric formatting from the PDF.
- **Table support** - extract repeated rows across table sections and continuation pages while keeping row order.
- **Review-friendly output** - keep uncertain relationships, unlabeled content, and review items visible instead of silently dropping them.
- **JSON and CSV export** - return structured JSON plus a flat CSV convenience format.
- **Web and CLI workflows** - use the browser workspace or run the same schema pipeline from the command line.

More detail is in [the application architecture](docs/application-architecture.md).

## Quick start

### Requirements

- Python 3.12+
- Node.js and npm
- `uv` for creating the Python environment
- An OpenRouter/LLM API key for schema-based extraction mode

### Install

From the project root:

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -r requirements.txt

cd frontend
npm install
cd ..
```
Set the API key when you want to use schema extraction

### Launch the web app

```bash
bash run_web_app.sh
```


## How it works

```text
PDF
  -> validate file, size, and page count
  -> parse with LiteParse and Docling
  -> build shared Markdown and table evidence
  -> automatic mapping or schema-driven mapping
  -> validate values against the processed source
  -> return JSON and CSV
  -> review and download in the workspace
```

The parser first tries native text extraction. If the result is empty,
corrupted, or the pipeline fails, the complete parse is retried with OCR so
text and table evidence come from the same extraction run.

The API returns the extracted result, CSV content, page count, elapsed time,
and processing metadata. The browser shows mapped fields, tables, review
items, and source-related notes before export.

## Automatic extraction

Automatic extraction makes no LLM calls. It uses:

- Markdown structure from LiteParse
- table structure and cell coordinates from Docling
- PDF coordinates to relate labels, values, and tables

When a relationship is uncertain, it remains in the review output. Unlabeled
source text is preserved so a user can inspect the complete result.

Use this mode when you want a quick structured result without writing a schema
or configuring an external model.

## Schema extraction

Schema extraction lets you describe the fields you want. You can upload a JSON
schema or build one in the web workspace. The schema is validated before the
PDF is processed and is not stored on the server.

The schema-driven path:

1. Parses the PDF locally with LiteParse and Docling.
2. Builds compact field, table-row, ambiguous, and short-text candidates.
3. Sends the schema and compact candidates to OpenRouter.
4. Checks the model response against the processed Markdown.
5. Preserves the exact source value and converts the result to JSON and CSV.

The normal schema path sends the model extracted candidates, not the original
PDF or the complete processed Markdown. The model chooses the best semantic
match; the local application remains responsible for source validation. If a
value cannot be matched safely, it is rejected instead of being invented.

### Schema shape

A schema contains document fields and may contain one repeated `records`
collection. The web API also accepts `table` as an alias for `records`.

JSON keeps document fields and records separate. CSV is flat: a document-only
schema produces one row, while a records schema produces one row per record
and repeats the document fields.

## CLI

The command-line flow accepts JSON or TOML schemas. It can also create a TOML
schema interactively.

Create a schema:

```bash
.venv/bin/python -m backend.run_pdf_to_outputs \
  --init-schema config/schema.toml
```

Extract the example document:

```bash
.venv/bin/python -m backend.run_pdf_to_outputs \
  --pdf examples/input1.pdf \
  --schema examples/input1.json \
  --output-dir output \
  --flat-output
```

Useful options include:

- `--ocr` - enable OCR explicitly.
- `--model MODEL` - select the OpenRouter model.
- `--save-markdown` - keep the merged Markdown used during extraction.
- `--flat-output` - write output files directly under `--output-dir`.

The CLI writes JSON and CSV files using the input filename as the output stem.

## Configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | API key for schema extraction | unset |
| `OPENROUTER_MODEL` | OpenRouter model name | application default |
| `NEXT_PUBLIC_API_URL` | API URL used by the frontend | `http://localhost:8000` |
| `FRONTEND_ORIGINS` | Comma-separated allowed browser origins | localhost and `127.0.0.1` on port 3000 |
| `MAX_PDF_BYTES` | Maximum PDF size | 25 MB |
| `MAX_PDF_PAGES` | Maximum PDF page count | 20 |
| `EXTRACTION_CONCURRENCY` | Maximum concurrent extraction jobs | 2 |
| `BACKEND_PORT` | Port used by `run_web_app.sh` | 8000 |
| `FRONTEND_PORT` | Port used by `run_web_app.sh` | 3000 |

The backend loads a root `.env` file when present. The launcher checks that
the selected backend and frontend ports are free before starting.

## Verification

Run the backend tests:

```bash
.venv/bin/python -m unittest tests.test_backend tests.test_generalized_extraction
```

Check and build the frontend:

```bash
cd frontend
npm run typecheck
npm run build
```

## Documentation

- [Application architecture](docs/application-architecture.md) - request flow, components, boundaries, and correctness decisions.
- [Architecture diagram](docs/application-architecture.svg) - the current visual architecture artifact.
- [Automatic field mapping plan](docs/automatic-field-mapping-plan.md) - deterministic mapping rules and review behavior.
- [Backend API](backend/main.py) - validation, extraction orchestration, and response assembly.
- [Hybrid parser](backend/hybrid_pdf_to_md.py) - LiteParse and Docling integration.
- [Schema model](backend/extraction_schema.py) - JSON/TOML schema validation and interactive creation.
- [Schema extractor](backend/schema_extractor.py) - compact evidence mapping, source validation, and CSV projection.

## Project layout

```text
backend/       FastAPI API, parsing, extraction, schemas, and CLI
frontend/      Next.js workspace and review interface
tests/         Backend and generalized extraction tests
examples/      Sample PDF, schema, and output files
docs/          Architecture and mapping documentation
```

## Acknowledgements

The extraction pipeline is built around [LiteParse](https://github.com/marker-ai/liteparse),
[Docling](https://github.com/docling-project/docling), [FastAPI](https://fastapi.tiangolo.com/),
and [Next.js](https://nextjs.org/).
