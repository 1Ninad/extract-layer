#!/usr/bin/env python3
"""Run the generalized PDF -> schema-driven JSON and CSV pipeline."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tempfile
from pathlib import Path

from extraction_schema import create_schema_interactively
from hybrid_pdf_to_md import build
from schema_extractor import (
    DEFAULT_MODEL,
    call_openrouter,
    csv_rows,
    load_dotenv,
    normalize_response,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = ROOT / "input_pdf"
DEFAULT_OUTPUT_DIR = ROOT / "output"
DEFAULT_SCHEMA = ROOT / "config" / "schema.toml"
MAX_EXTRACTION_ATTEMPTS = 3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, help="One PDF to process")
    parser.add_argument("--schema", type=Path, help="TOML extraction schema")
    parser.add_argument("--init-schema", type=Path, help="Create a TOML schema interactively and exit")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--ocr", action="store_true", help="Enable OCR in LiteParse and Docling")
    parser.add_argument("--liteparse", help="LiteParse executable; defaults to LIT_BIN, LITEPARSE_BIN, lit, or liteparse")
    parser.add_argument("--model", default=os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL))
    parser.add_argument("--api-key", default=os.environ.get("OPENROUTER_API_KEY"))
    parser.add_argument("--save-markdown", action="store_true", help="Keep intermediate Markdown under output/markdown")
    parser.add_argument(
        "--flat-output",
        action="store_true",
        help="Write JSON, CSV, and saved Markdown directly under --output-dir",
    )
    return parser.parse_args()


def select_pdf(explicit: Path | None, input_dir: Path) -> Path:
    if explicit is not None:
        pdf = explicit.resolve()
        if not pdf.is_file():
            raise ValueError(f"PDF not found: {pdf}")
        if pdf.suffix.lower() != ".pdf":
            raise ValueError(f"Input is not a PDF: {pdf}")
        return pdf

    pdfs = sorted(path for path in input_dir.rglob("*") if path.is_file() and path.suffix.lower() == ".pdf")
    if not pdfs:
        raise ValueError(f"No PDFs found in {input_dir}; pass --pdf PATH")
    if len(pdfs) > 1:
        choices = ", ".join(str(path) for path in pdfs)
        raise ValueError(f"Found multiple PDFs in {input_dir}; pass --pdf PATH. Found: {choices}")
    return pdfs[0].resolve()


def write_outputs(
    result: dict[str, object], schema, output_dir: Path, flat_output: bool = False
) -> tuple[Path, Path]:
    extracted_dir = output_dir if flat_output else output_dir / "extracted"
    extracted_dir.mkdir(parents=True, exist_ok=True)
    output_stem = f"{Path(str(result['source_file'])).stem}_output"
    json_path = extracted_dir / f"{output_stem}.json"
    csv_path = extracted_dir / f"{output_stem}.csv"

    columns, rows = csv_rows(result, schema)
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)
    return json_path, csv_path


def extract_result(pdf_path: Path, markdown: str, schema, api_key: str, model: str) -> dict[str, object]:
    last_error: ValueError | None = None
    for attempt in range(1, MAX_EXTRACTION_ATTEMPTS + 1):
        response = call_openrouter(markdown, schema, api_key, model)
        try:
            return normalize_response(response, markdown, schema, pdf_path.name)
        except ValueError as exc:
            last_error = exc
            if attempt == MAX_EXTRACTION_ATTEMPTS:
                raise
            print(
                f"Structured response failed source validation on attempt {attempt}; "
                "retrying the same extraction...",
                flush=True,
            )
    assert last_error is not None
    raise last_error


def run(args: argparse.Namespace) -> tuple[Path, Path]:
    load_dotenv(ROOT / ".env")
    if args.init_schema:
        create_schema_interactively(args.init_schema.resolve())
        raise SystemExit(0)

    schema_path = (args.schema or DEFAULT_SCHEMA).resolve()
    from extraction_schema import ExtractionSchema

    schema = ExtractionSchema.from_toml(schema_path)
    pdf_path = select_pdf(args.pdf, args.input_dir.resolve())
    api_key = args.api_key or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is required (set it in the environment, .env, or --api-key)")

    output_dir = args.output_dir.resolve()
    print(f"Extracting {pdf_path} with schema {schema.name!r}...", flush=True)
    if args.save_markdown and args.flat_output:
        with tempfile.TemporaryDirectory(prefix="pdf-litparse-") as temp_dir:
            hybrid_path = build(pdf_path, Path(temp_dir), args.liteparse, args.ocr)
            markdown = hybrid_path.read_text(encoding="utf-8")
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / f"{pdf_path.stem}_output.md").write_text(markdown, encoding="utf-8")
    elif args.save_markdown:
        markdown_dir = output_dir / "markdown" / pdf_path.stem
        hybrid_path = build(pdf_path, markdown_dir, args.liteparse, args.ocr)
        markdown = hybrid_path.read_text(encoding="utf-8")
    else:
        with tempfile.TemporaryDirectory(prefix="pdf-litparse-") as temp_dir:
            hybrid_path = build(pdf_path, Path(temp_dir), args.liteparse, args.ocr)
            markdown = hybrid_path.read_text(encoding="utf-8")
            result = extract_result(pdf_path, markdown, schema, api_key, args.model)
            paths = write_outputs(result, schema, output_dir, args.flat_output)
            print(f"Wrote {paths[0]}", flush=True)
            print(f"Wrote {paths[1]}", flush=True)
            return paths

    result = extract_result(pdf_path, markdown, schema, api_key, args.model)
    paths = write_outputs(result, schema, output_dir, args.flat_output)
    print(f"Wrote {paths[0]}", flush=True)
    print(f"Wrote {paths[1]}", flush=True)
    return paths


def main() -> None:
    try:
        run(parse_args())
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
