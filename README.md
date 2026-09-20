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

This application converts digitally-generated PDFs into CSV and JSON - ready for use-cases like update databases, etc.

Upload a PDF, choose how you want to extract it, and review the result in the web. You can let the application find fields automatically or define a schema. The application is layout-agnostic.

## Features

- **Two extraction modes** - use deterministic automatic extraction or define a schema for a focused result.
- **PDF-aware parsing** - combine LiteParse text with Docling tables and PDF coordinates.
- **OCR fallback** - retry the complete parsing flow with OCR when native text is not usable.
- **Source-faithful values** - keep spelling, punctuation, symbols, spaces, and numeric formatting sourced-from the PDF.
- **Table support** - extract rows across table sections and continuation pages while keeping row order.
- **JSON and CSV export** - return structured JSON and CSV.
- **Web and CLI workflows** - use the browser app or run the same schema pipeline from the command line.

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


## Automatic extraction mode

Automatic extraction makes no LLM calls. It uses:

- Markdown structure from LiteParse
- table structure and cell coordinates from Docling
- PDF coordinates to relate labels, values, and tables

When a relationship is uncertain, it remains in the review output. Unlabeled
source text is preserved so a user can inspect the complete result.

Use this mode when you want a quick structured result without writing a schema
or configuring an external model.

## Schema extraction mode

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
``