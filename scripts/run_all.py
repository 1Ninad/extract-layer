#!/usr/bin/env python3
"""Run the hybrid LiteParse-text / Docling-table PDF pipeline."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> None:
    print("$", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=ROOT / "input_pdf")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output")
    parser.add_argument("--ocr", action="store_true", help="Enable OCR in both parsers")
    parser.add_argument("--liteparse", help="LiteParse executable; defaults to lit or liteparse")
    args = parser.parse_args()

    pdfs = sorted(args.input_dir.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"No PDFs found in {args.input_dir}")

    for pdf in pdfs:
        stem_dir = args.output_dir / "markdown" / pdf.stem
        command = [sys.executable, "scripts/hybrid_pdf_to_md.py", str(pdf), str(stem_dir)]
        if args.liteparse:
            command.extend(["--liteparse", args.liteparse])
        if args.ocr:
            command.append("--ocr")
        run(command)


if __name__ == "__main__":
    main()
