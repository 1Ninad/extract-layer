#!/usr/bin/env python3
"""Run the complete PDF -> Markdown -> OpenRouter -> Excel pipeline."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_NODE_DIR = Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node"
DEFAULT_NODE = os.environ.get("CODEX_NODE", str(RUNTIME_NODE_DIR / "bin" / "node"))
DEFAULT_NODE_MODULES = os.environ.get("CODEX_NODE_MODULES", str(RUNTIME_NODE_DIR / "node_modules"))


def run(command: list[str]) -> None:
    print("$", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=ROOT / "input_pdf")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output")
    parser.add_argument(
        "--excel-output",
        type=Path,
        default=ROOT / "output" / "excel" / "all_certificates.xlsx",
        help="Final Excel workbook path",
    )
    parser.add_argument("--ocr", action="store_true", help="Enable OCR in both parsers")
    parser.add_argument("--liteparse", help="LiteParse executable; defaults to lit or liteparse")
    parser.add_argument("--model", help="OpenRouter model; otherwise OPENROUTER_MODEL or the mapper default is used")
    parser.add_argument("--node", default=DEFAULT_NODE, help="Node executable for the Excel writer")
    parser.add_argument("--node-modules", default=DEFAULT_NODE_MODULES, help="Directory containing @oai/artifact-tool")
    parser.add_argument("--mapping-json", type=Path, help="Optional validated LLM mapping JSON")
    args = parser.parse_args()

    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    excel_output = args.excel_output.resolve()
    pdfs = sorted(input_dir.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"No PDFs found in {input_dir}")

    markdown_paths: list[Path] = []
    for pdf in pdfs:
        stem_dir = output_dir / "markdown" / pdf.stem
        extraction_command = [sys.executable, "scripts/hybrid_pdf_to_md.py", str(pdf), str(stem_dir)]
        if args.liteparse:
            extraction_command.extend(["--liteparse", args.liteparse])
        if args.ocr:
            extraction_command.append("--ocr")
        run(extraction_command)
        markdown_paths.append(stem_dir / "hybrid.md")

    mapper_command = [
        sys.executable,
        "scripts/markdown_to_excel.py",
        *[str(path) for path in markdown_paths],
        "--output",
        str(excel_output),
        "--node",
        args.node,
        "--node-modules",
        args.node_modules,
    ]
    if args.model:
        mapper_command.extend(["--model", args.model])
    if args.mapping_json:
        mapper_command.extend(["--mapping-json", str(args.mapping_json.resolve())])
    run(mapper_command)
    print(f"Completed {len(pdfs)} PDF(s): {excel_output}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
