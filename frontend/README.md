# Document to Database frontend

This is the browser client for the existing PDF extraction pipeline.

## Run locally

```bash
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

Run the API in another terminal from the repository root:

```bash
python -m pip install -r backend/requirements.txt
uvicorn backend.app:app --reload --port 8000
```

The frontend sends one PDF and the schema definition as multipart form data to `POST /api/extract`. The API invokes the existing `scripts/run_pdf_to_outputs.py` runner, so LiteParse, Docling, and OpenRouter remain in one pipeline.
