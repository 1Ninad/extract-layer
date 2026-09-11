#!/usr/bin/env python3
"""Build Markdown with LiteParse text and Docling tables."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from docling_tables import extract, table_markdown


ROOT = Path(__file__).resolve().parents[1]


def _liteparse_command(explicit: str | None) -> str:
    if explicit:
        return explicit
    for environment_name in ("LIT_BIN", "LITEPARSE_BIN"):
        configured = os.environ.get(environment_name)
        if configured:
            return configured
    for candidate in ("lit", "liteparse"):
        if shutil.which(candidate):
            return candidate
    raise FileNotFoundError("Neither 'lit' nor 'liteparse' was found on PATH; set LIT_BIN")


def run_liteparse(input_pdf: Path, output_md: Path, binary: str | None, use_ocr: bool) -> None:
    output_md.parent.mkdir(parents=True, exist_ok=True)
    command = [
        _liteparse_command(binary),
        "parse",
        str(input_pdf),
        "--format",
        "markdown",
        "-o",
        str(output_md),
    ]
    if not use_ocr:
        command.append("--no-ocr")
    print("$", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def _is_separator_row(line: str) -> bool:
    if not line.lstrip().startswith("|"):
        return False
    cells = line.strip().strip("|").split("|")
    return bool(cells) and all(re.fullmatch(r"\s*:?-{3,}:?\s*", cell) for cell in cells)


def _markdown_table_blocks(markdown: str) -> list[tuple[int, int]]:
    lines = markdown.splitlines()
    blocks: list[tuple[int, int]] = []
    index = 0
    while index + 1 < len(lines):
        if lines[index].lstrip().startswith("|") and _is_separator_row(lines[index + 1]):
            end = index + 2
            while end < len(lines) and lines[end].lstrip().startswith("|"):
                end += 1
            blocks.append((index, end))
            index = end
        else:
            index += 1
    return blocks


def _tokens(value: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[\w]+", value, flags=re.UNICODE) if len(token) > 1}


def _table_score(block: str, table: dict[str, Any]) -> int:
    table_text = table_markdown(table)
    shared = len(_tokens(block) & _tokens(table_text))
    exact_cells = sum(
        3
        for row in table.get("rows", [])
        for value in row.values()
        if value and str(value) in block
    )
    return shared + exact_cells


def merge_markdown(liteparse_markdown: str, records: list[dict[str, Any]]) -> str:
    """Replace LiteParse Markdown tables and append any unmatched Docling tables.

    LiteParse sometimes emits a table as ordinary text or a fenced block when
    the PDF layout is difficult. Those text fragments remain part of the
    LiteParse body. Every Markdown table region, however, is replaced with its
    matching Docling table so the mapper has one authoritative tabular version.
    """

    lines = liteparse_markdown.splitlines()
    blocks = _markdown_table_blocks(liteparse_markdown)
    used: set[int] = set()
    replacements: dict[int, tuple[int, int, str]] = {}
    for start, end in blocks:
        block_text = "\n".join(lines[start:end])
        candidates = [
            (index, _table_score(block_text, record["table"]))
            for index, record in enumerate(records)
            if index not in used
        ]
        if not candidates:
            continue
        table_index, score = max(candidates, key=lambda item: item[1])
        # Do not mistake small metadata tables (orders, addresses, etc.) for a
        # Docling result table merely because they share generic words such as
        # "Property" or a short numeric token. A real match has several exact
        # data-cell overlaps in addition to header/token overlap.
        if score >= 10:
            used.add(table_index)
            record = records[table_index]
            page = record.get("page", "?")
            replacement = f"<!-- Docling table; source page {page} -->\n{table_markdown(record['table'])}"
            replacements[start] = (start, end, replacement)

    output: list[str] = []
    index = 0
    while index < len(lines):
        replacement = replacements.get(index)
        if replacement:
            _, end, value = replacement
            output.extend(value.splitlines())
            index = end
        else:
            output.append(lines[index])
            index += 1

    unmatched = [record for index, record in enumerate(records) if index not in used]
    if unmatched:
        output.extend(["", "## Tables (Docling; authoritative)", ""])
        for offset, record in enumerate(unmatched, start=1):
            page = record.get("page", "?")
            output.extend(
                [
                    f"### Table {offset} (source page {page})",
                    "",
                    f"<!-- Docling table; source page {page} -->",
                    table_markdown(record["table"]),
                    "",
                ]
            )
    return "\n".join(output).strip() + "\n"


def build(input_pdf: Path, output_dir: Path, liteparse_binary: str | None = None, use_ocr: bool = False) -> Path:
    input_pdf = input_pdf.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    liteparse_md = output_dir / "liteparse.md"
    run_liteparse(input_pdf, liteparse_md, liteparse_binary, use_ocr)
    records = extract(
        input_pdf,
        output_dir / "docling_tables.json",
        output_dir / "docling_tables.md",
        use_ocr=use_ocr,
    )
    hybrid_md = output_dir / "hybrid.md"
    hybrid_md.write_text(merge_markdown(liteparse_md.read_text(encoding="utf-8"), records), encoding="utf-8")
    return hybrid_md


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_pdf", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--liteparse", help="LiteParse executable; defaults to LIT_BIN, LITEPARSE_BIN, lit, or liteparse")
    parser.add_argument("--ocr", action="store_true", help="Enable OCR in both parsers")
    args = parser.parse_args()
    build(args.input_pdf, args.output_dir, args.liteparse, args.ocr)


if __name__ == "__main__":
    main()
