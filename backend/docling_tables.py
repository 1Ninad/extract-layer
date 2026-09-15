#!/usr/bin/env python3
"""Extract Docling tables while retaining layout evidence for mapping."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .clean_docling_output import clean_text


def _integer(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _page_info(raw_document: dict[str, Any], page_no: int | None) -> dict[str, Any]:
    pages = raw_document.get("pages", {})
    page = pages.get(str(page_no), {}) if isinstance(pages, dict) and page_no is not None else {}
    size = page.get("size", {}) if isinstance(page, dict) else {}
    return {
        "page": page_no,
        "width": float(size.get("width", 0) or 0),
        "height": float(size.get("height", 0) or 0),
        "rotation": _integer(page.get("rotation", 0)) if isinstance(page, dict) else 0,
    }


def _normal_bbox(raw_bbox: Any, page: dict[str, Any]) -> dict[str, float] | None:
    if not isinstance(raw_bbox, dict):
        return None
    try:
        left = float(raw_bbox["l"])
        right = float(raw_bbox["r"])
        first = float(raw_bbox["t"])
        second = float(raw_bbox["b"])
    except (KeyError, TypeError, ValueError):
        return None
    origin = str(raw_bbox.get("coord_origin", "TOPLEFT")).upper()
    if origin == "BOTTOMLEFT" and page.get("height"):
        top = page["height"] - max(first, second)
        bottom = page["height"] - min(first, second)
    else:
        top = min(first, second)
        bottom = max(first, second)
    box = {"left": min(left, right), "top": top, "right": max(left, right), "bottom": bottom}
    rotation = page.get("rotation", 0) % 360
    width = page.get("width", 0)
    height = page.get("height", 0)
    if rotation == 90:
        return {"left": height - box["bottom"], "top": box["left"], "right": height - box["top"], "bottom": box["right"]}
    if rotation == 180:
        return {"left": width - box["right"], "top": height - box["bottom"], "right": width - box["left"], "bottom": height - box["top"]}
    if rotation == 270:
        return {"left": box["top"], "top": width - box["right"], "right": box["bottom"], "bottom": width - box["left"]}
    return box


def _table_page(raw_table: dict[str, Any]) -> int | None:
    provenance = raw_table.get("prov", [])
    if provenance and isinstance(provenance[0], dict):
        return _integer(provenance[0].get("page_no"), 0) or None
    return None


def _grid_dimensions(raw_table: dict[str, Any]) -> tuple[int, int, list[dict[str, Any]]]:
    data = raw_table.get("data", {})
    raw_cells = data.get("table_cells", []) if isinstance(data, dict) else []
    if not isinstance(raw_cells, list):
        return 0, 0, []
    cells = [cell for cell in raw_cells if isinstance(cell, dict)]
    row_count = _integer(data.get("num_rows")) if isinstance(data, dict) else 0
    col_count = _integer(data.get("num_cols")) if isinstance(data, dict) else 0
    row_count = max(row_count, max((_integer(cell.get("end_row_offset_idx")) for cell in cells), default=0))
    col_count = max(col_count, max((_integer(cell.get("end_col_offset_idx")) for cell in cells), default=0))
    return max(row_count, 0), max(col_count, 0), cells


def _cell_record(cell: dict[str, Any], page: dict[str, Any]) -> dict[str, Any]:
    start_row = _integer(cell.get("start_row_offset_idx"))
    start_col = _integer(cell.get("start_col_offset_idx"))
    end_row = max(start_row + 1, _integer(cell.get("end_row_offset_idx"), start_row + 1))
    end_col = max(start_col + 1, _integer(cell.get("end_col_offset_idx"), start_col + 1))
    row_span = max(1, _integer(cell.get("row_span"), end_row - start_row))
    col_span = max(1, _integer(cell.get("col_span"), end_col - start_col))
    text = clean_text(cell.get("text"))
    return {
        "text": text,
        "page": page.get("page"),
        "row_index": start_row,
        "column_index": start_col,
        "row_span": row_span,
        "column_span": col_span,
        "end_row_index": end_row,
        "end_column_index": end_col,
        "bbox": _normal_bbox(cell.get("bbox"), page),
        "column_header": bool(cell.get("column_header", False)),
        "row_header": bool(cell.get("row_header", False)),
        "row_section": bool(cell.get("row_section", False)),
        "fillable": bool(cell.get("fillable", False)),
        "status": "value" if text else "empty",
    }


def _grid_from_table(
    raw_table: dict[str, Any], page: dict[str, Any]
) -> tuple[list[list[dict[str, Any] | None]], list[dict[str, Any]]]:
    row_count, col_count, raw_cells = _grid_dimensions(raw_table)
    if not row_count or not col_count:
        return [], []

    matrix: list[list[dict[str, Any] | None]] = [[None for _ in range(col_count)] for _ in range(row_count)]
    anchors: list[dict[str, Any]] = []
    for raw_cell in raw_cells:
        cell = _cell_record(raw_cell, page)
        row = cell["row_index"]
        col = cell["column_index"]
        if not (0 <= row < row_count and 0 <= col < col_count):
            continue
        anchors.append(cell)
        for covered_row in range(row, min(row_count, cell["end_row_index"])):
            for covered_col in range(col, min(col_count, cell["end_column_index"])):
                if matrix[covered_row][covered_col] is not None:
                    continue
                if covered_row == row and covered_col == col:
                    matrix[covered_row][covered_col] = cell
                    continue
                matrix[covered_row][covered_col] = {
                    "text": "",
                    "page": page.get("page"),
                    "row_index": covered_row,
                    "column_index": covered_col,
                    "row_span": 1,
                    "column_span": 1,
                    "end_row_index": covered_row + 1,
                    "end_column_index": covered_col + 1,
                    "bbox": cell["bbox"],
                    "column_header": cell["column_header"],
                    "row_header": cell["row_header"],
                    "row_section": cell["row_section"],
                    "fillable": cell["fillable"],
                    "status": "covered",
                    "covered_by": {"row": row, "column": col},
                }
    return matrix, anchors


def _header_rows(anchors: list[dict[str, Any]], row_count: int) -> list[int]:
    flagged = sorted({cell["row_index"] for cell in anchors if cell["column_header"]})
    return flagged or ([0] if row_count else [])


def _header_labels(anchors: list[dict[str, Any]], columns: int, header_rows: list[int]) -> list[str]:
    labels: list[str] = []
    for column in range(columns):
        parts: list[str] = []
        for row in header_rows:
            for cell in anchors:
                if cell["row_index"] != row or not (cell["column_index"] <= column < cell["end_column_index"]):
                    continue
                value = str(cell["text"])
                if value and value not in parts:
                    parts.append(value)
        labels.append(" / ".join(parts) or f"Column {column + 1}")
    return labels


def _generic_table(raw_table: dict[str, Any], raw_document: dict[str, Any]) -> dict[str, Any]:
    page_number = _table_page(raw_table)
    page = _page_info(raw_document, page_number)
    grid, anchors = _grid_from_table(raw_table, page)
    if not grid:
        return {"name": "table", "columns": [], "rows": []}

    width = len(grid[0])
    header_rows = _header_rows(anchors, len(grid))
    columns = _header_labels(anchors, width, header_rows)
    for row_index, row in enumerate(grid):
        for column_index, cell in enumerate(row):
            if cell is None:
                row[column_index] = {
                    "text": "",
                    "page": page.get("page"),
                    "row_index": row_index,
                    "column_index": column_index,
                    "row_span": 1,
                    "column_span": 1,
                    "end_row_index": row_index + 1,
                    "end_column_index": column_index + 1,
                    "bbox": None,
                    "column_header": row_index in header_rows,
                    "row_header": False,
                    "row_section": False,
                    "fillable": False,
                    "status": "uncertain",
                }
    values_grid = [[cell["text"] if cell and cell["status"] == "value" else "" for cell in row] for row in grid]
    rows = [dict(zip(columns, values)) for index, values in enumerate(values_grid) if index not in header_rows]
    provenance = raw_table.get("prov", [])
    raw_table_bbox = provenance[0].get("bbox") if provenance and isinstance(provenance[0], dict) else None
    return {
        "name": "table",
        "row_count": len(grid),
        "column_count": width,
        "columns": columns,
        "rows": rows,
        "grid_values": values_grid,
        "cell_grid": grid,
        "header_rows": header_rows,
        "header_structure": [[values_grid[row][column] for column in range(width)] for row in header_rows],
        "bbox": _normal_bbox(raw_table_bbox, page),
        "bboxes": [{"page": page_number, "bbox": _normal_bbox(raw_table_bbox, page)}],
        "page": page_number,
        "pages": [page_number] if page_number is not None else [],
        "page_dimensions": page,
    }


def table_from_raw(raw_table: dict[str, Any], raw_document: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a clean table plus its stable grid and source provenance."""

    return _generic_table(raw_table, raw_document or {})


def _table_signature(table: dict[str, Any]) -> tuple[Any, ...]:
    return (
        len(table.get("columns", [])),
        tuple(str(value).strip().casefold() for value in table.get("columns", [])),
        tuple(tuple(str(value).strip().casefold() for value in row) for row in table.get("header_structure", [])),
    )


def _is_page_continuation(previous: dict[str, Any], current: dict[str, Any]) -> bool:
    previous_pages = previous.get("pages", [])
    current_pages = current.get("pages", [])
    if not previous_pages or not current_pages or current_pages[0] != previous_pages[-1] + 1:
        return False
    previous_box = previous.get("bbox") or {}
    current_box = current.get("bbox") or {}
    previous_width = float((previous.get("page_dimensions") or {}).get("width", 0) or 0)
    current_width = float((current.get("page_dimensions") or {}).get("width", 0) or 0)
    if not previous_box or not current_box or not previous_width or not current_width:
        return False
    previous_left = previous_box["left"] / previous_width
    previous_right = previous_box["right"] / previous_width
    current_left = current_box["left"] / current_width
    current_right = current_box["right"] / current_width
    return abs(previous_left - current_left) <= 0.12 and abs(previous_right - current_right) <= 0.12


def _data_grid(table: dict[str, Any]) -> list[list[str]]:
    header_rows = set(table.get("header_rows", table.get("header_structure", [])))
    return [
        row
        for index, row in enumerate(table.get("grid_values", []))
        if index not in header_rows
    ]


def _merge_repeated_tables(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for record in records:
        table = record["table"]
        previous = merged[-1] if merged else None
        if previous and _table_signature(previous["table"]) == _table_signature(table) and _is_page_continuation(previous["table"], table):
            previous_table = previous["table"]
            current_data = _data_grid(table)
            previous_data = previous_table.get("_last_data_grid", _data_grid(previous_table))
            current_key = tuple(tuple(row) for row in current_data) if current_data else None
            seen_data = previous_table.setdefault(
                "_seen_data_grids",
                {tuple(tuple(row) for row in previous_data)} if previous_data else set(),
            )
            if current_key is not None and current_key in seen_data:
                previous_table["pages"] = list(dict.fromkeys(previous_table.get("pages", []) + table.get("pages", [])))
                previous_table.setdefault("bboxes", []).extend(table.get("bboxes", []))
                previous_table.setdefault("duplicate_pages", []).extend(table.get("pages", []))
                continue
            previous_table["rows"].extend(table.get("rows", []))
            previous_table["grid_values"].extend(
                row for index, row in enumerate(table.get("grid_values", [])) if index not in table.get("header_rows", [])
            )
            previous_table["cell_grid"].extend(
                row for index, row in enumerate(table.get("cell_grid", [])) if index not in table.get("header_rows", [])
            )
            previous_table["row_count"] = len(previous_table.get("grid_values", []))
            previous_table["pages"] = list(dict.fromkeys(previous_table.get("pages", []) + table.get("pages", [])))
            previous_table["bboxes"].extend(table.get("bboxes", []))
            previous_table["_last_data_grid"] = current_data
            if current_key is not None:
                seen_data.add(current_key)
            continue
        merged.append(record)
        table["_last_data_grid"] = _data_grid(table)
    for record in merged:
        record["table"].pop("_last_data_grid", None)
        record["table"].pop("_seen_data_grids", None)

    unique: list[dict[str, Any]] = []
    seen_copies: dict[tuple[Any, ...], int] = {}
    for record in merged:
        table = record["table"]
        data = _data_grid(table)
        key = (_table_signature(table), tuple(tuple(row) for row in data)) if data else None
        existing_index = seen_copies.get(key) if key is not None else None
        if existing_index is None:
            if key is not None:
                seen_copies[key] = len(unique)
            unique.append(record)
            continue
        existing_table = unique[existing_index]["table"]
        existing_table["pages"] = list(dict.fromkeys(existing_table.get("pages", []) + table.get("pages", [])))
        existing_table.setdefault("bboxes", []).extend(table.get("bboxes", []))
        existing_table.setdefault("duplicate_pages", []).extend(table.get("pages", []))
        existing_table.setdefault("duplicate_pages", []).extend(table.get("duplicate_pages", []))
    return unique


def table_records(raw_document: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for raw_table in raw_document.get("tables", []):
        if not isinstance(raw_table, dict):
            continue
        table = table_from_raw(raw_table, raw_document)
        if not table["columns"]:
            continue
        records.append({"page": table.get("page"), "table": table})
    return _merge_repeated_tables(records)


def table_markdown(table: dict[str, Any]) -> str:
    columns = table["columns"]
    rows = table["rows"]

    def markdown_cell(value: Any) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ").strip()

    lines = [
        "| " + " | ".join(markdown_cell(column) for column in columns) + " |",
        "|" + "|".join("---" for _ in columns) + "|",
    ]
    lines.extend(
        "| " + " | ".join(markdown_cell(row.get(column, "")) for column in columns) + " |"
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
    converter = DocumentConverter(format_options={"pdf": PdfFormatOption(pipeline_options=options)})
    result = converter.convert(str(input_pdf))
    raw_document = result.document.export_to_dict()
    records = table_records(raw_document)

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(
            {
                "source_file": input_pdf.name,
                "pages": raw_document.get("pages", {}),
                "texts": raw_document.get("texts", []),
                "tables": records,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
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
    extract(args.input_pdf, args.output_dir / "docling_tables.json", args.output_dir / "docling_tables.md", use_ocr=args.ocr)


if __name__ == "__main__":
    main()
