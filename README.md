# Generic PDF Schema Extraction

This project converts digitally-generated PDFs into schema-driven JSON and
unformatted CSV. LiteParse supplies document text and Docling supplies table
structure. An OpenRouter model maps the merged Markdown into a user-defined
schema.

The extractor preserves printed values. It does not translate, calculate,
normalize dates, convert units, round numbers, or invent missing values.

## Web application

The repository includes a FastAPI backend and a separate Next.js frontend.
The API calls the same validated LiteParse + Docling + OpenRouter pipeline as
the command-line runner.

Run both services from the repository root with one command:

```bash
bash run_web_app.sh
```

Then open `http://127.0.0.1:3000`. Press `Ctrl-C` to stop both services.

The launcher builds the frontend with the configured API URL before starting
the production server.

Start the backend from the repository root:

```bash
source .venv/bin/activate
uvicorn backend.main:app --reload --port 8000
```

In a second terminal, start the frontend:

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Open `http://localhost:3000`. Upload one PDF (maximum 20 pages), define the
document and optional repeated-record fields, then select **Extract data**.
The result can be reviewed as a table or JSON and downloaded as JSON or CSV.

The backend reads `OPENROUTER_API_KEY` and optional `OPENROUTER_MODEL` from the
root environment or `.env`. `FRONTEND_ORIGINS` controls allowed browser origins.
Interactive API documentation is available at `http://localhost:8000/docs`.

## Setup

Use Python 3.12 on macOS for the broadest wheel compatibility:

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

Set `OPENROUTER_API_KEY` in the environment or in `.env`.

## Create a schema

Create a readable TOML schema with the guided wizard:

```bash
python -m backend.run_pdf_to_outputs --init-schema config/invoice.toml
```

The wizard asks for an overall document description and each field's name,
type, and distinguishing description. Supported types are `text`, `number`,
`date`, `boolean`, `array`, and `object`. Arrays may contain scalar values or
nested objects, which is useful for tables.

The example input in this repository is `examples/input.pdf`, with its
reusable extraction schema in `examples/input.toml`. Run it with:

```bash
.venv/bin/python -m backend.run_pdf_to_outputs \
  --pdf examples/input.pdf \
  --schema examples/input.toml \
  --output-dir examples \
  --save-markdown \
  --flat-output
```

This reads `examples/input.pdf` using `examples/input.toml` and writes:

```text
examples/input_output.json
examples/input_output.csv
examples/input_output.md
```

The schema uses a compact repeated-record layout. A different PDF gets its
output shape from its own TOML schema; the extraction code does not contain
document- or field-specific rules.

A schema can contain document-level fields and, in `records` mode, a repeated
record group for line items or table rows:

```toml
schema_version = 1
name = "invoice"
description = "Extract invoice identifiers and line items."
output_mode = "records"

[[fields]]
name = "invoice_number"
type = "text"
description = "The supplier's invoice identifier, not the purchase order or delivery number."

[records]
name = "line_items"
description = "One record for each separately listed product or service line."

[[records.fields]]
name = "description"
type = "text"
description = "The exact product or service description for this line."

[[records.fields]]
name = "quantity"
type = "number"
description = "The printed quantity for this line, preserving decimals and trailing zeroes."
```

Descriptions should explain how to distinguish a field from similar values in
the document. Values are returned exactly as printed even when their declared
type is `number` or `date`.

Field names may use either machine-friendly underscores (`invoice_number`) or
human-readable spaces (`Invoice Number`). The name is preserved exactly in the
JSON keys and CSV headers.

## Run extraction

Process one PDF explicitly:

```bash
python -m backend.run_pdf_to_outputs \
  --pdf input_pdf/invoice.pdf \
  --schema config/invoice.toml
```

If `input_pdf/` contains exactly one PDF, `--pdf` can be omitted:

```bash
python -m backend.run_pdf_to_outputs --schema config/invoice.toml
```

Useful options:

- `--ocr` enables OCR in both parsers.
- `--liteparse PATH` selects a LiteParse executable.
- `--model MODEL` selects the OpenRouter model.
- `--api-key KEY` supplies the OpenRouter key directly.
- `--output-dir PATH` changes the output root.
- `--save-markdown` keeps intermediate Markdown under `output/markdown/`.

Outputs are written under `output/extracted/`:

```text
invoice_output.json
invoice_output.csv
```

Output filenames use the input PDF stem with `_output` appended. For example,
`invoice.pdf` produces `invoice_output.json` and `invoice_output.csv`.

JSON keeps document fields and records separate. CSV is flattened: document
mode produces one row, while records mode produces one row per record and
repeats document-level fields. Arrays are stored as compact JSON strings in
CSV cells. Every CSV includes `source_file` for provenance.

The runner treats the LLM response as a candidate location, not as the final
value. Exact matches are accepted directly. When the model adds harmless
connective words or changes whitespace/case/punctuation, the normalizer
projects the candidate back onto a unique source span and writes the Markdown
value to JSON/CSV. It can also recover a complete source span when the model
omits non-numeric descriptive words inside that span. Numeric tokens must still
match exactly; ambiguous or unsupported values fail validation. Final JSON and CSV files are not written
when schema, response, or source-projection validation fails. The generalized
path retries a source-validation failure up to three total extraction attempts,
using the same Markdown and prompt; it does not send the original PDF.

The web API first runs LiteParse and Docling with native text extraction. If
that complete extraction pass fails, it reruns both parsers with OCR enabled.
The response includes a processing note showing whether native extraction or
the OCR fallback produced the result.
