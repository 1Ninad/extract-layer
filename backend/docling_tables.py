#!/usr/bin/env python3
"""Extract only table data from Docling's PDF document model.

Docling still has to inspect the PDF layout internally to find tables, but this
module never uses Docling's document-level text export.  The persisted output
contains table data only; the surrounding document text comes from LiteParse.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .clean_docling_output import clean_text


def _grid_from_table(raw_table: dict[str, Any]) -> list[list[str]]:
    data = raw_table.get("data", {})
    cells = data.get("table_cells", []) if isinstance(data, dict) else []
    if not isinstance(cells, list):
        return []

    def integer(cell: dict[str, Any], key: str) -> int:
        try:
            return int(cell.get(key, 0))
        except (TypeError, ValueError):
            return 0

    row_count = integer(data, "num_rows") if isinstance(data, dict) else 0
    col_count = integer(data, "num_cols") if isinstance(data, dict) else 0
    row_count = max(
        row_count,
        max((integer(cell, "end_row_offset_idx") for cell in cells if isinstance(cell, dict)), default=0),
    )
    col_count = max(
        col_count,
        max((integer(cell, "end_col_offset_idx") for cell in cells if isinstance(cell, dict)), default=0),
    )
    if not row_count or not col_count:
        return []

    matrix = [["" for _ in range(col_count)] for _ in range(row_count)]
    for cell in cells:
        if not isinstance(cell, dict):
            continue
        row = integer(cell, "start_row_offset_idx")
        col = integer(cell, "start_col_offset_idx")
        if 0 <= row < row_count and 0 <= col < col_count:
            # A spanning cell is represented once, at its top-left position.
            # This matches Docling's Markdown export and avoids duplicating
            # labels such as a two-column "Specifications" heading.
            matrix[row][col] = clean_text(cell.get("text"))
    return matrix


def _generic_table(raw_table: dict[str, Any]) -> dict[str, Any]:
    grid = _grid_from_table(raw_table)
    if not grid:
        return {"name": "table", "columns": [], "rows": []}

    width = max(len(row) for row in grid)
    header = (grid[0] + [""] * width)[:width]
    columns: list[str] = []
    for index, value in enumerate(header, start=1):
        columns.append(value or f"Column {index}")

    rows = []
    for values in grid[1:]:
        padded = (values + [""] * width)[:width]
        if any(padded):
            rows.append(dict(zip(columns, padded)))
    return {"name": "table", "columns": columns, "rows": rows}


def table_from_raw(raw_table: dict[str, Any]) -> dict[str, Any]:
    """Return a clean table object suitable for Markdown and JSON output."""

    return _generic_table(raw_table)


def table_records(raw_document: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for raw_table in raw_document.get("tables", []):
        if not isinstance(raw_table, dict):
            continue
        table = table_from_raw(raw_table)
        if not table["columns"] or not table["rows"]:
            continue
        provenance = raw_table.get("prov", [])
        page = provenance[0].get("page_no") if provenance and isinstance(provenance[0], dict) else None
        records.append({"page": page, "table": table})
    return records


def table_markdown(table: dict[str, Any]) -> str:
    columns = table["columns"]
    rows = table["rows"]
    lines = [
        "| " + " | ".join(str(column) for column in columns) + " |",
        "|" + "|".join("---" for _ in columns) + "|",
    ]
    lines.extend(
        "| " + " | ".join(str(row.get(column, "")) for column in columns) + " |"
        for row in rows
    )
    return "\n".join(lines)


def tables_markdown(records: list[dict[str, Any]]) -> str:
    sections = []
    for index, record in enumerate(records, start=1):
        page = record.get("page", "?")
        sections.append(f"<!-- Docling table {index}; source page {page} -->\n{table_markdown(record['table'])}")
    return "\n\n".join(sections) + ("\n" if sections else "")


def extract(
    input_pdf: Path,
    output_json: Path,
    output_md: Path,
    use_ocr: bool = False,
) -> list[dict[str, Any]]:
    from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
    from docling.document_converter import DocumentConverter, PdfFormatOption

    options = PdfPipelineOptions(do_ocr=use_ocr, do_table_structure=True)
    options.table_structure_options.mode = TableFormerMode.ACCURATE
    options.table_structure_options.do_cell_matching = False
    converter = DocumentConverter(
        format_options={"pdf": PdfFormatOption(pipeline_options=options)}
    )
    result = converter.convert(str(input_pdf))
    records = table_records(result.document.export_to_dict())

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps({"source_file": input_pdf.name, "tables": records}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(tables_markdown(records), encoding="utf-8")
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_pdf", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--ocr", action="store_true", help="Enable full-page OCR")
    args = parser.parse_args()
    output_dir = args.output_dir
    extract(
        args.input_pdf,
        output_dir / "docling_tables.json",
        output_dir / "docling_tables.md",
        use_ocr=args.ocr,
    )


if __name__ == "__main__":
    main()
