"""HTTP API for the document-to-database extraction pipeline.

The existing command-line runner remains the source of truth. This service
validates a browser schema, writes a temporary TOML schema, invokes the
runner, and returns the generated JSON and CSV for the frontend.
"""

from __future__ import annotations

import csv
import io
import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_pdf_to_outputs.py"
MAX_FILE_BYTES = 25 * 1024 * 1024

app = FastAPI(title="Document to Database API", version="1.0.0")
allowed_origins = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "pipeline": "LiteParse + Docling + OpenRouter"}


@app.post("/api/extract")
async def extract(
    file: UploadFile = File(...),
    schema: str = Form(...),
    ocr: bool = Form(False),
    model: str | None = Form(None),
) -> dict[str, Any]:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Upload one PDF file.")
    if not RUNNER.exists():
        raise HTTPException(status_code=500, detail="The extraction runner is not available.")

    try:
        schema_mapping = json.loads(schema)
        validate_schema_mapping(schema_mapping)
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    pdf_bytes = await file.read()
    if len(pdf_bytes) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="PDF must be 25 MB or smaller.")

    job_id = uuid.uuid4().hex[:12]
    with tempfile.TemporaryDirectory(prefix=f"document-to-database-{job_id}-") as temp_name:
        temp_dir = Path(temp_name)
        pdf_path = temp_dir / Path(file.filename).name
        schema_path = temp_dir / "schema.toml"
        output_dir = temp_dir / "output"
        pdf_path.write_bytes(pdf_bytes)
        schema_path.write_text(mapping_to_toml(schema_mapping), encoding="utf-8")

        command = [
            sys.executable,
            str(RUNNER),
            "--pdf",
            str(pdf_path),
            "--schema",
            str(schema_path),
            "--output-dir",
            str(output_dir),
            "--flat-output",
        ]
        if ocr:
            command.append("--ocr")
        if model:
            command.extend(["--model", model])

        process = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
            timeout=180,
        )
        if process.returncode != 0:
            detail = (process.stderr or process.stdout).strip()
            raise HTTPException(status_code=422, detail=detail[-3000:] or "Extraction failed.")

        json_path = output_dir / f"{pdf_path.stem}_output.json"
        csv_path = output_dir / f"{pdf_path.stem}_output.csv"
        if not json_path.exists() or not csv_path.exists():
            raise HTTPException(status_code=500, detail="The runner completed without producing outputs.")

        result = json.loads(json_path.read_text(encoding="utf-8"))
        csv_text = csv_path.read_text(encoding="utf-8")
        return {
            "job_id": job_id,
            "source_file": file.filename,
            "result": result,
            "csv": csv_text,
            "json_filename": json_path.name,
            "csv_filename": csv_path.name,
        }


def validate_schema_mapping(schema: Any) -> None:
    if not isinstance(schema, dict):
        raise ValueError("Schema must be a JSON object.")
    if not schema.get("name") or not schema.get("description"):
        raise ValueError("Schema name and description are required.")
    if schema.get("output_mode") not in {"document", "records"}:
        raise ValueError("output_mode must be 'document' or 'records'.")
    if not isinstance(schema.get("fields"), list):
        raise ValueError("Schema fields must be an array.")
    validate_fields(schema["fields"], "document")
    records = schema.get("records")
    if schema["output_mode"] == "records":
        if not isinstance(records, dict) or not isinstance(records.get("fields"), list):
            raise ValueError("Record mode requires a records field group.")
        validate_fields(records["fields"], "records")


def validate_fields(fields: list[Any], location: str) -> None:
    names: set[str] = set()
    valid_types = {"text", "number", "date", "boolean", "array", "object"}
    for field in fields:
        if not isinstance(field, dict):
            raise ValueError(f"Every {location} field must be an object.")
        name = field.get("name", "")
        if not name or not name.replace("_", "a").isalnum() or name[0].isdigit():
            raise ValueError(f"Invalid {location} field name: {name!r}.")
        if name in names:
            raise ValueError(f"Duplicate {location} field: {name}.")
        names.add(name)
        if field.get("type") not in valid_types:
            raise ValueError(f"Unsupported type for {location}.{name}.")
        if not str(field.get("description", "")).strip():
            raise ValueError(f"Description is required for {location}.{name}.")


def mapping_to_toml(schema: dict[str, Any]) -> str:
    lines = [
        "schema_version = 1",
        f"name = {toml_string(schema['name'])}",
        f"description = {toml_string(schema['description'])}",
        f"output_mode = {toml_string(schema['output_mode'])}",
    ]
    for field in schema["fields"]:
        append_field(lines, "fields", field)
    if schema["output_mode"] == "records":
        records = schema["records"]
        lines.extend([
            "",
            "[records]",
            f"name = {toml_string(records['name'])}",
            f"description = {toml_string(records['description'])}",
        ])
        for field in records["fields"]:
            append_field(lines, "records.fields", field)
    return "\n".join(lines) + "\n"


def append_field(lines: list[str], prefix: str, field: dict[str, Any]) -> None:
    lines.extend([
        "",
        f"[[{prefix}]]",
        f"name = {toml_string(field['name'])}",
        f"type = {toml_string(field['type'])}",
        f"description = {toml_string(field['description'])}",
    ])
    if field.get("type") == "array":
        lines.append(f"item_type = {toml_string(field.get('item_type', 'text'))}")


def toml_string(value: str) -> str:
    return json.dumps(str(value), ensure_ascii=False)
