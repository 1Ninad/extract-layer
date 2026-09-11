#!/usr/bin/env python3
"""Send one raw PDF directly to OpenRouter and write the fixed Excel schema."""

from __future__ import annotations

import argparse
import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import markdown_to_excel as mapper


OPENROUTER_URL = mapper.OPENROUTER_URL


def _call_openrouter_pdf(pdf_path: Path, api_key: str, model: str) -> dict[str, Any]:
    encoded_pdf = base64.b64encode(pdf_path.read_bytes()).decode("ascii")
    prompt = mapper._prompt(
        "The source PDF is attached to this request. Read the values directly from the PDF."
    )
    messages = [
        prompt[0],
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt[1]["content"]},
                {
                    "type": "file",
                    "file": {
                        "filename": pdf_path.name,
                        "file_data": f"data:application/pdf;base64,{encoded_pdf}",
                    },
                },
            ],
        },
    ]
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "response_format": {"type": "json_schema", "json_schema": mapper._json_schema()},
        "provider": {"require_parameters": True},
        "plugins": [{"id": "file-parser", "pdf": {"engine": "native"}}],
    }
    model_name = model.rsplit("/", 1)[-1].lower()
    if not model_name.startswith("gpt-5"):
        payload["temperature"] = 0

    request = urllib.request.Request(
        OPENROUTER_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/openrouter",
            "X-OpenRouter-Title": "Direct PDF certificate mapper",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenRouter HTTP {exc.code}: {detail[:1500]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenRouter request failed: {exc.reason}") from exc

    try:
        response_json = json.loads(body)
        content = response_json["choices"][0]["message"].get("content")
        parsed = json.loads(content)
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Invalid structured response from OpenRouter: {body[:1500]}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("OpenRouter response JSON must be an object")
    return parsed


def _normalize(response: dict[str, Any], pdf_path: Path) -> dict[str, Any]:
    raw_rows = response.get("rows")
    if not isinstance(raw_rows, list) or not raw_rows:
        raise ValueError("LLM response must contain a non-empty rows array")

    rows: list[dict[str, str]] = []
    for index, raw_row in enumerate(raw_rows, start=1):
        if not isinstance(raw_row, dict):
            raise ValueError(f"LLM row {index} is not an object")
        missing = set(mapper.EXCEL_COLUMNS) - set(raw_row)
        unexpected = set(raw_row) - set(mapper.EXCEL_COLUMNS)
        if missing or unexpected:
            raise ValueError(
                f"LLM row {index} schema mismatch; missing={sorted(missing)}, unexpected={sorted(unexpected)}"
            )
        row: dict[str, str] = {}
        for column in mapper.EXCEL_COLUMNS:
            value = raw_row[column]
            if not isinstance(value, str):
                raise ValueError(f"LLM row {index} field {column!r} is not a string")
            max_length = mapper.MAX_LENGTHS.get(column)
            if max_length is not None and len(value) > max_length:
                raise ValueError(
                    f"LLM row {index} field {column!r} exceeds its schema limit of {max_length} characters"
                )
            row[column] = value
        # No local text extraction is performed in direct-PDF mode.
        row["FileName"] = pdf_path.name
        rows.append(row)
    return {"columns": mapper.EXCEL_COLUMNS, "rows": rows, "source_pdf": str(pdf_path)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default=os.environ.get("OPENROUTER_MODEL", mapper.DEFAULT_MODEL))
    parser.add_argument("--api-key", default=os.environ.get("OPENROUTER_API_KEY"))
    parser.add_argument("--node", help="Node executable used by the Excel writer")
    parser.add_argument("--node-modules", help="Directory containing @oai/artifact-tool")
    parser.add_argument("--mapping-json", type=Path)
    args = parser.parse_args()
    mapper._load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    api_key = args.api_key or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY is required")
    pdf_path = args.pdf.resolve()
    if not pdf_path.is_file():
        raise SystemExit(f"PDF not found: {pdf_path}")

    print(f"Mapping raw PDF {pdf_path} with {args.model}...", flush=True)
    mapping = _normalize(_call_openrouter_pdf(pdf_path, api_key, args.model), pdf_path)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.mapping_json:
        args.mapping_json.resolve().parent.mkdir(parents=True, exist_ok=True)
        args.mapping_json.resolve().write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")
    mapper.write_excel(mapping, output, args.node, args.node_modules)
    print(f"Wrote {len(mapping['rows'])} row(s) to {output}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", flush=True)
        raise SystemExit(1) from exc
