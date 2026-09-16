# PDF extraction

This application turns PDFs into structured JSON and CSV.

It has two modes:

- **Automatic extraction** finds fields and tables without an LLM.
- **Schema extraction** uses a user-uploaded JSON schema and an LLM to return only the requested values.

Values are kept as printed. The application does not translate, calculate,
round, convert units, or invent missing values.

## Run the web app

From the project root:

```bash
bash run_web_app.sh
```

Open `http://127.0.0.1:3000`.

The launcher starts the Next.js frontend and FastAPI backend. The backend uses
LiteParse and Docling to process PDFs. Set `OPENROUTER_API_KEY` in the root
environment or `.env` when using schema extraction.

To run the services separately:

```bash
source .venv/bin/activate
uvicorn backend.main:app --reload --port 8000
```

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

## Schema extraction

After uploading a PDF, choose **Use a JSON schema** and upload a `.json` file.
The file is read in the browser, validated locally and by the backend, and is
not stored on the server.

The simple schema format has document fields and one optional repeated table:

```json
{
  "schema_version": 1,
  "name": "invoice",
  "description": "Extract invoice details and line items.",
  "fields": [
    {"name": "invoice_number", "description": "The printed invoice number."},
    {"name": "invoice_date", "description": "The printed invoice date."}
  ],
  "table": {
    "name": "line_items",
    "description": "Each product or service row.",
    "fields": [
      {"name": "description", "description": "The product or service description."},
      {"name": "quantity", "description": "The printed quantity."}
    ]
  }
}
```

Required properties are `schema_version`, `name`, `description`, and
`fields`. `table` is optional. Field `type` is optional and defaults to
`text`. Supported types are `text`, `number`, `date`, `boolean`, `array`, and
`object`.

Schema JSON keeps document fields and table rows separate. CSV is a flat
convenience format: document-only schemas produce one row, while table schemas
produce one row per table record and repeat the document fields.

The CLI also accepts JSON or TOML schemas:

```bash
.venv/bin/python -m backend.run_pdf_to_outputs \
  --pdf examples/input1.pdf \
  --schema examples/input1.json \
  --output-dir examples \
  --flat-output
```

## When the LLM is used

The LLM is used only for schema extraction.

The processing path is:

```text
PDF -> LiteParse and Docling -> local field/table candidates
    -> schema + compact candidates -> LLM mapping
    -> validation against local Markdown -> JSON and CSV
```

The LLM receives:

- the overall schema description
- every requested field name and description
- every table name, description, and field definition
- declared field types
- compact extracted label/value candidates
- reconstructed table headers and rows
- short unresolved text candidates and ambiguous field values

It does not receive the original PDF or the complete processed Markdown in the
normal schema path. Coordinates, cell metadata, long unlabeled prose, and other
parser internals are removed before the model call.

The LLM decides which source value matches a field semantically. For example,
a field called `company_name` can match a PDF label such as `Manufacturer` if
the description makes that meaning clear. Repeated records must remain aligned
to their source table rows, and source-line order is retained when a nearby
field supplies context inherited by a following table.

The LLM response is treated as a candidate location, not as trusted output.
The backend checks the expected keys, checks that returned values exist in the
processed Markdown, preserves the source spelling and formatting, rejects
unsupported numeric changes, and retries invalid responses. If a value cannot
be safely matched to the source, extraction fails rather than silently
inventing a value.

This reduces model input most for documents containing substantial prose or
parser metadata. A short document made almost entirely of requested tables may
see little token reduction because the table cells still need to be supplied.

## Automatic mapping

Automatic extraction is deterministic and makes no LLM calls. It combines:

- Markdown structure from LiteParse
- table structure and coordinates from Docling
- PDF coordinates for field and table relationships

Uncertain relationships go to Review. Unlabeled source text is preserved. The
full design and correctness rules are documented in
`docs/automatic-field-mapping-plan.md`.

## Limits and configuration

- PDFs are limited to 20 pages and 25 MB by default.
- Schema files are limited to 1 MB in the web app.
- `OPENROUTER_MODEL` selects the schema extraction model.
- `FRONTEND_ORIGINS` controls allowed browser origins.
- API documentation is available at `http://localhost:8000/docs`.

## Verification

```bash
.venv/bin/python -m unittest tests.test_backend tests.test_generalized_extraction
cd frontend && npm run typecheck && npm run build
```
