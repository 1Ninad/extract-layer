#!/usr/bin/env python3
"""Create clean, compact outputs from Docling's raw document export."""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path


TABLE_COLUMNS = ["Characteristic", "Method", "Result", "Unit", "Min", "Max"]


def clean_text(value: object) -> str:
    text = str(value or "")
    text = re.sub(r"(?:\\_)+|_+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _table_grid(raw: dict[str, object]) -> list[list[str]]:
    for table in raw.get("tables", []):
        grid_rows = table.get("data", {}).get("grid", []) if isinstance(table, dict) else []
        if not isinstance(grid_rows, list):
            continue
        grid = [cell for row in grid_rows if isinstance(row, list) for cell in row if isinstance(cell, dict)]
        if not any("Characteristic" in clean_text(cell.get("text")) for cell in grid):
            continue
        max_row = max((int(cell.get("end_row_offset_idx", 0)) for cell in grid if isinstance(cell, dict)), default=0)
        max_col = max((int(cell.get("end_col_offset_idx", 0)) for cell in grid if isinstance(cell, dict)), default=0)
        matrix = [["" for _ in range(max_col)] for _ in range(max_row)]
        for cell in grid:
            if not isinstance(cell, dict):
                continue
            row = int(cell.get("start_row_offset_idx", 0))
            col = int(cell.get("start_col_offset_idx", 0))
            if row < max_row and col < max_col:
                matrix[row][col] = clean_text(cell.get("text"))
        return matrix
    return []


def characteristic_table(raw: dict[str, object]) -> dict[str, object]:
    grid = _table_grid(raw)
    rows: list[dict[str, str]] = []
    for row in grid:
        if len(row) < 6 or not any(row):
            continue
        if row[0] == "Characteristic":
            continue
        if not any(row[:4]) and row[4:6] == ["Min", "Max"]:
            continue
        values = (row + [""] * 6)[:6]
        rows.append(dict(zip(TABLE_COLUMNS, values)))

    # Some PDFs place a two-line label partly in the preceding row. If the
    # same label appears in a later row, keep it only on the later row.
    labels = [row["Characteristic"] for row in rows]
    for index, label in enumerate(labels):
        for later in labels[index + 1 :]:
            if later and later != label and later in label:
                rows[index]["Characteristic"] = clean_text(label.replace(later, ""))
                break

    return {"name": "characteristic_results", "columns": TABLE_COLUMNS, "rows": rows}


def table_markdown(table: dict[str, object]) -> str:
    columns = table["columns"]
    rows = table["rows"]
    lines = ["| " + " | ".join(columns) + " |", "|" + "|".join("---" for _ in columns) + "|"]
    lines.extend("| " + " | ".join(str(row.get(column, "")) for column in columns) + " |" for row in rows)
    return "\n".join(lines)


def table_html(table: dict[str, object]) -> str:
    columns = table["columns"]
    rows = table["rows"]
    head = "".join(f"<th>{html.escape(str(column))}</th>" for column in columns)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(column, '')))}</td>" for column in columns) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def clean_markdown(source: str, table: dict[str, object]) -> str:
    start = source.find("| Characteristic")
    end = source.find("<!-- image -->", start)
    if start >= 0 and end >= 0:
        source = source[:start] + table_markdown(table) + "\n\n" + source[end:]
    source = re.sub(r"<!-- image -->\s*", "", source)
    source = re.sub(r"^\s*(?:\\_){3,}\s*$", "", source, flags=re.MULTILINE)
    source = re.sub(r"\n{3,}", "\n\n", source)
    return source.strip() + "\n"


def clean_html(source: str, table: dict[str, object]) -> str:
    body_match = re.search(r"<body[^>]*>(.*?)</body>", source, flags=re.IGNORECASE | re.DOTALL)
    body = body_match.group(1) if body_match else source
    body = re.sub(r"<table>.*?</table>", table_html(table), body, count=1, flags=re.IGNORECASE | re.DOTALL)
    body = re.sub(r"\s*<p>\s*_+\s*</p>\s*", "\n", body, flags=re.IGNORECASE)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Clean certificate of analysis</title>
  <style>
    body {{ font-family: system-ui, sans-serif; line-height: 1.45; max-width: 1000px; margin: 2rem auto; padding: 0 1rem; }}
    table {{ border-collapse: collapse; margin: 1rem 0; width: 100%; }}
    th, td {{ border: 1px solid #777; padding: .45rem .6rem; text-align: left; vertical-align: top; }}
    th {{ background: #f1f1f1; }}
  </style>
</head>
<body>
{body.strip()}
</body>
</html>
"""


def clean(input_json: Path, input_md: Path, input_html: Path, output_dir: Path) -> None:
    raw = json.loads(input_json.read_text(encoding="utf-8"))
    table = characteristic_table(raw)
    clean_json = {"source_file": output_dir.name + ".pdf", "tables": [table]}
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "docling_clean.json").write_text(json.dumps(clean_json, indent=2) + "\n", encoding="utf-8")
    (output_dir / "docling_clean.md").write_text(clean_markdown(input_md.read_text(encoding="utf-8"), table), encoding="utf-8")
    (output_dir / "docling_clean.html").write_text(clean_html(input_html.read_text(encoding="utf-8"), table), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    clean(args.output_dir / "docling.json", args.output_dir / "docling.md", args.output_dir / "docling.html", args.output_dir)


if __name__ == "__main__":
    main()
