## Notes
- Use /design-taste-frontend skill for any frontend task.
- Keep code simple, reusable, and any specific PDF-agnostic. Do not hardcode one document's layout or fields.
- Keep comments short, clear, precise, and natural. Add them only when they explain important or non-obvious logic.
- Keep the frontend usable on both mobile and desktop.
- Before Git/GitHub push, update README.md file & AGENTS.md's Repository Map section (if any changes required)/
- Commit message should be within 8 words. Should be simple, easy to understand quickly, clear, crisp, precise, natural, and by real human.
- I like clean, minimalist, rich, tech. enterprise-ready frontend.

## Repository map

Read the tree progressively.

```text
AGENTS.md — agent entry point and navigation rules
README.md — product behavior, setup, commands, schemas, and outputs
backend/
├── main.py — FastAPI endpoints, validation, OCR fallback, and response assembly
├── hybrid_pdf_to_md.py — LiteParse + Docling parsing boundary and merged Markdown
├── automatic_extraction.py — deterministic automatic fields, tables, confidence, review, and deduplication
├── docling_tables.py — Docling table normalization, coordinates, headers, and continuations
├── clean_docling_output.py — compact Docling JSON/Markdown/HTML helpers
├── extraction_schema.py — TOML schema model, validation, nested fields, and wizard
├── schema_extractor.py — compact evidence mapping, OpenRouter calls, source validation, normalization, and CSV rows
└── run_pdf_to_outputs.py — CLI flow, input selection, retries, and output files
frontend/
├── app/
│   ├── page.tsx — upload/example flow, API call, loading, and error state
│   ├── layout.tsx — application shell and metadata
│   ├── globals.css — global responsive styling
│   └── api/example/ — demo schema and PDF routes
├── components/ — document panel, extraction mode, schema upload, results, and export menu
└── lib/
    ├── types.ts — API, schema, and extraction result contracts
    ├── schema.ts — JSON schema parsing, validation, summary, and example schema
    ├── demo.ts and example-data.ts — demo response and example payloads
    └── download.ts — browser download helper
tests/
├── test_backend.py — API, validation, and processing-mode contracts
└── test_generalized_extraction.py — schema, normalization, projection, and output contracts
docs/
├── application-architecture.md/.dot/.svg — current request architecture and editable diagram
└── automatic-field-mapping-plan.md — automatic-mapping design decisions and direction
examples/
├── input1.pdf and input1.json — reusable sample document and schema
└── output1.* — reference output artifacts
input_pdf/tp/
└── schema_*.json — upload-ready schemas for certificate examples
requirements.txt — Dependencies
frontend/package.json — frontend scripts and dependencies
run_web_app.sh — local full-stack launcher
```

The extraction flow is: PDF → LiteParse/Docling → automatic extraction or compact-evidence schema mapping → JSON/CSV → Next.js review/download UI.


## Guardrails

- Prefer targeted `rg` searches and caller/import tracing. Read nearby tests before changing behavior.
- Update the closest source-of-truth doc when a stable behavior or design decision changes.
- Ignore `.venv/`, `frontend/node_modules/`, `.git/`, `__pycache__/`, `.DS_Store`, generated output, and `.env`. Never expose `.env` contents.
