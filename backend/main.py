"""FastAPI adapter for automatic and schema-driven PDF extraction."""

from __future__ import annotations

import asyncio
import csv
import io
import json
import os
import tempfile
import time
import unicodedata
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field as PydanticField
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]

from .extraction_schema import ExtractionSchema
from .schema_extractor import (
    DEFAULT_MODEL,
    call_openrouter,
    csv_rows,
    load_dotenv,
    normalize_response,
)


MAX_PDF_BYTES = int(os.environ.get("MAX_PDF_BYTES", 25 * 1024 * 1024))
MAX_PDF_PAGES = int(os.environ.get("MAX_PDF_PAGES", 20))
EXTRACTION_CONCURRENCY = int(os.environ.get("EXTRACTION_CONCURRENCY", 2))
semaphore = asyncio.Semaphore(EXTRACTION_CONCURRENCY)

load_dotenv(ROOT / ".env")

app = FastAPI(
    title="Document to Database API",
    version="1.0.0",
    description="Deterministic automatic extraction with a compatible schema-driven mode.",
)

allowed_origins = [
    value.strip()
    for value in os.environ.get(
        "FRONTEND_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if value.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class SchemaPayload(BaseModel):
    schema_version: int = 1
    name: str
    description: str
    output_mode: str | None = None
    fields: list[dict[str, Any]] = PydanticField(default_factory=list)
    records: dict[str, Any] | None = None
    table: dict[str, Any] | None = None


def _validated_schema(raw: str | dict[str, Any]) -> ExtractionSchema:
    try:
        mapping = json.loads(raw) if isinstance(raw, str) else raw
        return ExtractionSchema.from_mapping(mapping)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _validate_pdf(content: bytes, filename: str) -> int:
    if not filename.lower().endswith(".pdf") or not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="Upload a valid PDF file.")
    if len(content) > MAX_PDF_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"PDF exceeds the {MAX_PDF_BYTES // (1024 * 1024)} MB limit.",
        )
    try:
        page_count = len(PdfReader(io.BytesIO(content)).pages)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="The PDF could not be read.") from exc
    if page_count > MAX_PDF_PAGES:
        raise HTTPException(
            status_code=422,
            detail=f"PDF has {page_count} pages; the maximum is {MAX_PDF_PAGES}.",
        )
    return page_count


def _to_csv(result: dict[str, object], schema: ExtractionSchema) -> str:
    columns, rows = csv_rows(result, schema)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="raise")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _run_extraction(
    content: bytes,
    filename: str,
    schema: ExtractionSchema | None,
    model: str,
    use_ocr: bool,
) -> tuple[dict[str, object], str, dict[str, object]]:
    """Run native extraction first, then retry the complete pipeline with OCR."""

    if schema is None:
        if use_ocr:
            result, csv_content = _run_automatic_extraction_once(content, filename, use_ocr=True)
            return result, csv_content, {
                "mode": "automatic_ocr_requested",
                "ocr_used": True,
                "note": "Automatic deterministic mapping used OCR-enabled LiteParse and Docling.",
            }
        try:
            result, csv_content = _run_automatic_extraction_once(content, filename, use_ocr=False)
        except Exception:
            print("Automatic native extraction failed; retrying with OCR enabled.", flush=True)
            try:
                result, csv_content = _run_automatic_extraction_once(content, filename, use_ocr=True)
            except Exception as ocr_error:
                raise RuntimeError(
                    "Automatic native extraction failed, and the OCR fallback also failed: "
                    f"{ocr_error}"
                ) from ocr_error
            return result, csv_content, {
                "mode": "automatic_ocr_fallback",
                "ocr_used": True,
                "note": "Automatic deterministic mapping used OCR after native extraction failed.",
            }
        return result, csv_content, {
            "mode": "automatic",
            "ocr_used": False,
            "note": "Automatic deterministic mapping used native text, Markdown structure, and PDF coordinates. No LLM was called.",
        }

    if use_ocr:
        result, csv_content = _run_extraction_once(
            content, filename, schema, model, use_ocr=True
        )
        return result, csv_content, {
            "mode": "ocr_requested",
            "ocr_used": True,
            "note": "OCR used. LiteParse and Docling processed this PDF with OCR enabled.",
        }

    try:
        result, csv_content = _run_extraction_once(
            content, filename, schema, model, use_ocr=False
        )
    except Exception:
        print(
            "Native extraction failed; retrying with LiteParse and Docling OCR enabled.",
            flush=True,
        )
        try:
            result, csv_content = _run_extraction_once(
                content, filename, schema, model, use_ocr=True
            )
        except Exception as ocr_error:
            raise RuntimeError(
                "Native extraction failed, and the OCR fallback also failed: "
                f"{ocr_error}"
            ) from ocr_error
        return result, csv_content, {
            "mode": "ocr_fallback",
            "ocr_used": True,
            "note": "OCR fallback used. The initial native-text extraction failed, so LiteParse and Docling were rerun with OCR enabled.",
        }

    return result, csv_content, {
        "mode": "native",
        "ocr_used": False,
        "note": "OCR not used. Native PDF text extraction succeeded.",
    }


def _run_extraction_once(
    content: bytes,
    filename: str,
    schema: ExtractionSchema,
    model: str,
    use_ocr: bool,
) -> tuple[dict[str, object], str]:
    # Docling is intentionally imported here so health and schema endpoints can
    # still diagnose configuration when the parser runtime is incomplete.
    from .hybrid_pdf_to_md import build

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is not configured on the server.")

    with tempfile.TemporaryDirectory(prefix="document-to-database-") as temp_dir:
        working_dir = Path(temp_dir)
        pdf_path = working_dir / Path(filename).name
        pdf_path.write_bytes(content)
        markdown_path = build(pdf_path, working_dir / "parsed", None, use_ocr)
        markdown = markdown_path.read_text(encoding="utf-8")
        if not use_ocr:
            _validate_native_markdown(markdown)
        last_error: ValueError | None = None
        for attempt in range(3):
            candidate = call_openrouter(markdown, schema, api_key, model)
            try:
                result = normalize_response(candidate, markdown, schema, pdf_path.name)
                break
            except ValueError as exc:
                last_error = exc
                if attempt == 2:
                    raise
        else:  # pragma: no cover - the loop either succeeds or raises
            assert last_error is not None
            raise last_error
        return result, _to_csv(result, schema)


def _run_automatic_extraction_once(
    content: bytes,
    filename: str,
    use_ocr: bool,
) -> tuple[dict[str, object], str]:
    from .automatic_extraction import extract_automatic
    from .hybrid_pdf_to_md import build

    with tempfile.TemporaryDirectory(prefix="document-to-database-automatic-") as temp_dir:
        working_dir = Path(temp_dir)
        pdf_path = working_dir / Path(filename).name
        pdf_path.write_bytes(content)
        markdown_path = build(pdf_path, working_dir / "parsed", None, use_ocr)
        artifact_path = working_dir / "parsed" / "docling_tables.json"
        artifacts = json.loads(artifact_path.read_text(encoding="utf-8"))
        markdown = markdown_path.read_text(encoding="utf-8")
        return extract_automatic(markdown, artifacts, artifacts.get("tables", []), pdf_path.name)


def _validate_native_markdown(markdown: str) -> None:
    """Reject empty or visibly corrupted native text before model extraction."""

    if not markdown.strip():
        raise ValueError("Native text extraction returned no usable text.")

    invalid_characters = [
        character
        for character in markdown
        if unicodedata.category(character) == "Cc" and character not in "\n\r\t"
    ]
    if invalid_characters:
        raise ValueError(
            "Native text extraction returned non-printable characters; "
            "the source text is not reliable."
        )


@app.get("/api/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "model": os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL),
        "max_pdf_pages": MAX_PDF_PAGES,
    }


@app.post("/api/schema/validate")
def validate_schema(payload: SchemaPayload) -> dict[str, bool]:
    _validated_schema(payload.model_dump())
    return {"valid": True}


@app.post("/api/extractions")
async def create_extraction(
    pdf: UploadFile = File(...),
    schema_payload: str | None = Form(None, alias="schema"),
    use_ocr: bool = Form(False),
) -> dict[str, object]:
    filename = Path(pdf.filename or "document.pdf").name
    content = await pdf.read(MAX_PDF_BYTES + 1)
    page_count = _validate_pdf(content, filename)
    parsed_schema = _validated_schema(schema_payload) if schema_payload and schema_payload.strip() else None
    model = os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)
    started = time.perf_counter()

    try:
        async with semaphore:
            result, csv_content, processing = await asyncio.to_thread(
                _run_extraction, content, filename, parsed_schema, model, use_ocr
            )
    except (OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "result": result,
        "csv": csv_content,
        "page_count": page_count,
        "elapsed_ms": round((time.perf_counter() - started) * 1000),
        "processing": processing,
    }
