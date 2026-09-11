#!/usr/bin/env python3
"""Temporary direct-PDF runner for CipherTestCert_1.pdf."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "input_pdf" / "CipherTestCert_1.pdf"
DEFAULT_EXCEL = ROOT / "output" / "excel" / "cipher_test_cert.xlsx"
RUNTIME_NODE_DIR = Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node"
DEFAULT_NODE = os.environ.get("CODEX_NODE", str(RUNTIME_NODE_DIR / "bin" / "node"))
DEFAULT_NODE_MODULES = os.environ.get("CODEX_NODE_MODULES", str(RUNTIME_NODE_DIR / "node_modules"))


def run(command: list[str]) -> None:
    print("$", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        default=os.environ.get("OPENROUTER_MODEL", "mistralai/mistral-small-24b-instruct-2501"),
    )
    parser.add_argument("--excel-output", type=Path, default=DEFAULT_EXCEL)
    parser.add_argument("--node", default=DEFAULT_NODE)
    parser.add_argument("--node-modules", default=DEFAULT_NODE_MODULES)
    parser.add_argument("--mapping-json", type=Path, help="Optional validated mapping JSON")
    args = parser.parse_args()

    if not PDF.is_file():
        raise SystemExit(f"Input PDF not found: {PDF}")

    excel_output = args.excel_output.resolve()
    direct_command = [
        sys.executable,
        "scripts/pdf_to_excel_direct.py",
        str(PDF),
        "--output",
        str(excel_output),
        "--model",
        args.model,
        "--node",
        args.node,
        "--node-modules",
        args.node_modules,
    ]
    if args.mapping_json:
        direct_command.extend(["--mapping-json", str(args.mapping_json.resolve())])
    run(direct_command)
    print(f"Completed: {excel_output}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
