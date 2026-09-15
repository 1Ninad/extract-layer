# Document to Database API

The API wraps the existing `scripts/run_pdf_to_outputs.py` pipeline. It does not duplicate extraction logic: LiteParse supplies document text, Docling supplies table structure, and the configured OpenRouter model maps the merged Markdown to the submitted schema.

## Run locally

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export OPENROUTER_API_KEY=replace-me
export LIT_BIN=/absolute/path/to/lit
uvicorn backend.app:app --reload --port 8000
```

Then start the Next.js app from `frontend/` with `npm install && npm run dev`.

## API

- `GET /api/health` checks that the service is reachable.
- `POST /api/extract` accepts multipart fields `file`, `schema`, and optional `ocr`/`model`. The response contains the structured JSON result and CSV text for client-side download.
