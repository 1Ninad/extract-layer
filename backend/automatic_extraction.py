"""Deterministic PDF mapping using Markdown structure and Docling geometry.

This module deliberately has no model or field dictionary.  It accepts a
relationship only when the source structure provides enough evidence and
keeps the original source in the review data when it does not.
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from typing import Any


_TOKEN_RE = re.compile(r"[\w]+(?:[-./][\w]+)*", re.UNICODE)
_SEPARATOR_RE = re.compile(r"^\s*(.{1,100}?)(?:\s*[:=])\s*(.*?)\s*$")
# Reserved extension point; v1 stays deterministic and cost-free.
LLM_FALLBACK_ENABLED = False
_MARKDOWN_TABLE_SEPARATOR = re.compile(r"^\s*:?-{3,}:?\s*$")


@dataclass(frozen=True)
class TextBlock:
    text: str
    page: int
    bbox: dict[str, float]
    label: str
    source: str


def _clean_markdown(value: str) -> str:
    value = re.sub(r"<!--.*?-->", "", value, flags=re.DOTALL)
    value = re.sub(r"!?(?:\*\*|__)(.*?)(?:\*\*|__)", r"\1", value)
    value = value.replace("**", "").replace("__", "")
    value = re.sub(r"`([^`]*)`", r"\1", value)
    value = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", value)
    return re.sub(r"\\([|*_])", r"\1", value).strip()


def _tokens(value: str) -> list[str]:
    return _TOKEN_RE.findall(value)


def _normal(value: str) -> str:
    return " ".join(_tokens(value)).casefold()


def _split_styled_label(value: str) -> list[str]:
    """Split adjacent colon-ended labels that PDF text joined together."""

    cleaned = _clean_markdown(value).strip()
    parts = [part.strip(" \t:;") for part in cleaned.split(":") if part.strip(" \t:;")]
    if len(parts) > 1 and all(_label_candidate(part) for part in parts):
        return parts
    return [cleaned]


def _label_candidate(value: str) -> bool:
    value = _clean_markdown(value).strip(" \t-–—")
    if "|" in value:
        return False
    tokens = _tokens(value)
    if not tokens or len(value) > 100 or len(tokens) > 9:
        return False
    letters = sum(character.isalpha() for character in value)
    if letters < 2 or letters / max(1, len(value)) < 0.35:
        return False
    if re.search(r"https?://|\b\d{2,}[/-]\d", value, flags=re.IGNORECASE):
        return False
    return True


def _value_like(value: str) -> bool:
    value = value.strip()
    if not value:
        return False
    if re.search(r"https?://|\S+@\S+", value, flags=re.IGNORECASE):
        return True
    if re.search(r"\b\d{1,4}[-/]\w{2,4}[-/]\d{1,4}\b", value):
        return True
    if re.search(r"(?:[$€£₹]\s*)?\d[\d,]*(?:\.\d+)?\s*%?", value):
        return True
    # Identifiers are supported only when their shape carries more than a
    # lone trailing number, which avoids guessing ordinary prose boundaries.
    return bool(re.search(r"[A-Za-z][A-Za-z0-9]*[-/][A-Za-z0-9./-]*\d[A-Za-z0-9./-]*", value))


def _split_pipes(line: str) -> list[str]:
    raw = line.strip()
    if raw.startswith("|"):
        raw = raw[1:]
    if raw.endswith("|") and not raw.endswith("\\|"):
        raw = raw[:-1]
    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for character in raw:
        if character == "|" and not escaped:
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(character)
        escaped = character == "\\" and not escaped
        if character != "\\":
            escaped = False
    cells.append("".join(current).strip())
    return [_clean_markdown(cell) for cell in cells]


def _is_table_separator(line: str) -> bool:
    return line.lstrip().startswith("|") and all(
        _MARKDOWN_TABLE_SEPARATOR.fullmatch(cell) for cell in _split_pipes(line)
    )


def _markdown_tables(markdown: str) -> tuple[list[dict[str, Any]], set[int]]:
    lines = markdown.splitlines()
    tables: list[dict[str, Any]] = []
    table_lines: set[int] = set()
    index = 0
    while index + 1 < len(lines):
        if lines[index].lstrip().startswith("|") and _is_table_separator(lines[index + 1]):
            end = index + 2
            while end < len(lines) and lines[end].lstrip().startswith("|"):
                end += 1
            rows = [_split_pipes(lines[row]) for row in range(index, end) if row != index + 1]
            tables.append({"line_start": index + 1, "line_end": end, "rows": rows})
            table_lines.update(range(index, end))
            index = end
        else:
            index += 1
    return tables, table_lines


def _markdown_fields(markdown: str, tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    for table in tables:
        for row_offset, row in enumerate(table["rows"]):
            if row_offset == 0:
                continue
            if len(row) == 2:
                column = 0
            elif len(row) == 3:
                column = 1
            else:
                continue
            label = row[column]
            value = row[column + 1].strip()
            if _label_candidate(label) and (value or column + 1 == len(row) - 1):
                fields.append(
                    {
                        "label": label,
                        "value": value,
                        "confidence": 0.91,
                        "evidence": ["markdown_table"],
                        "source": {"kind": "markdown", "row": table["line_start"] + row_offset},
                    }
                )

    lines = markdown.splitlines()
    for line_number, raw_line in enumerate(lines, start=1):
        if line_number - 1 in {line - 1 for table in tables for line in range(table["line_start"], table["line_end"])}:
            continue
        line = _clean_markdown(raw_line)
        if not line or line.startswith("#") or line == "---" or line.startswith("<!--"):
            continue
        styled_fields: list[tuple[str, str]] = []
        for styled_match in re.finditer(r"(?:\*\*|__)([^*_]+)(?:\*\*|__)\s+([^*|]+)", raw_line):
            styled_value = _clean_markdown(styled_match.group(2))
            styled_labels = _split_styled_label(styled_match.group(1))
            for label_index, styled_label in enumerate(styled_labels):
                field_value = styled_value if label_index == len(styled_labels) - 1 else ""
                styled_fields.append((_normal(styled_label), field_value))
                if not _label_candidate(styled_label):
                    continue
                fields.append(
                    {
                        "label": styled_label,
                        "value": field_value,
                        "confidence": 0.9,
                        "evidence": ["markdown_style"],
                        "source": {"kind": "markdown", "line": line_number, "text": _clean_markdown(styled_match.group(0))},
                    }
                )
        styled_segments = re.split(r"(?=(?:\*\*|__))", raw_line) if re.search(r"\*\*|__", raw_line) else [raw_line]
        segments: list[str] = []
        for styled_segment in styled_segments:
            cleaned_segment = _clean_markdown(styled_segment)
            segments.extend(part.strip() for part in cleaned_segment.split("|"))
        for segment in segments:
            match = _SEPARATOR_RE.match(segment)
            if not match:
                continue
            label, value = match.groups()
            if not _label_candidate(label):
                continue
            if any(_normal(label) == styled_label for styled_label, _ in styled_fields):
                continue
            fields.append(
                {
                    "label": label.strip(),
                    "value": value.strip(),
                    "confidence": 0.86,
                    "evidence": ["markdown_separator"],
                    "source": {"kind": "markdown", "line": line_number, "text": segment},
                }
            )
    return fields


def _page_dimensions(raw_document: dict[str, Any]) -> dict[int, dict[str, Any]]:
    pages = raw_document.get("pages", {})
    result: dict[int, dict[str, Any]] = {}
    if not isinstance(pages, dict):
        return result
    for key, page in pages.items():
        if not isinstance(page, dict):
            continue
        try:
            number = int(page.get("page_no", key))
        except (TypeError, ValueError):
            continue
        size = page.get("size", {})
        result[number] = {
            "width": float(size.get("width", 0) or 0),
            "height": float(size.get("height", 0) or 0),
            "rotation": int(page.get("rotation", 0) or 0),
        }
    return result


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
    if str(raw_bbox.get("coord_origin", "TOPLEFT")).upper() == "BOTTOMLEFT" and page.get("height"):
        top = page["height"] - max(first, second)
        bottom = page["height"] - min(first, second)
    else:
        top = min(first, second)
        bottom = max(first, second)
    box = {"left": min(left, right), "top": top, "right": max(left, right), "bottom": bottom}
    rotation = int(page.get("rotation", 0) or 0) % 360
    width = page.get("width", 0)
    height = page.get("height", 0)
    if rotation == 90:
        return {"left": height - box["bottom"], "top": box["left"], "right": height - box["top"], "bottom": box["right"]}
    if rotation == 180:
        return {"left": width - box["right"], "top": height - box["bottom"], "right": width - box["left"], "bottom": height - box["top"]}
    if rotation == 270:
        return {"left": box["top"], "top": width - box["right"], "right": box["bottom"], "bottom": width - box["left"]}
    return box


def _text_blocks(raw_document: dict[str, Any], table_records: list[dict[str, Any]]) -> list[TextBlock]:
    dimensions = _page_dimensions(raw_document)
    table_boxes = [
        (record["table"].get("page"), record["table"].get("bbox"))
        for record in table_records
    ]
    blocks: list[TextBlock] = []
    for item in raw_document.get("texts", []):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or item.get("orig") or "").strip()
        provenance = item.get("prov", [])
        if not text or not isinstance(provenance, list):
            continue
        spans = []
        for entry in provenance:
            if not isinstance(entry, dict):
                continue
            page = int(entry.get("page_no", 0) or 0)
            bbox = _normal_bbox(entry.get("bbox"), dimensions.get(page, {}))
            if bbox:
                spans.append((page, bbox, entry.get("charspan")))
        if not spans:
            continue
        for span_index, (page, bbox, charspan) in enumerate(spans):
            start, end = (charspan if isinstance(charspan, list) and len(charspan) == 2 else (0, len(text)))
            fragment = text[int(start):int(end)].strip() if len(spans) > 1 else text
            if not fragment:
                continue
            if _inside_table(page, bbox, table_boxes):
                continue
            blocks.append(TextBlock(fragment, page, bbox, str(item.get("label", "text")), f"docling:{span_index}"))
    return _dedupe_blocks(blocks)


def _inside_table(page: int, bbox: dict[str, float], table_boxes: list[tuple[Any, Any]]) -> bool:
    for table_page, table_bbox in table_boxes:
        if page != table_page or not isinstance(table_bbox, dict):
            continue
        horizontal = min(bbox["right"], table_bbox["right"]) - max(bbox["left"], table_bbox["left"])
        vertical = min(bbox["bottom"], table_bbox["bottom"]) - max(bbox["top"], table_bbox["top"])
        area = max(1.0, (bbox["right"] - bbox["left"]) * (bbox["bottom"] - bbox["top"]))
        if horizontal > 0 and vertical > 0 and horizontal * vertical / area > 0.65:
            return True
    return False


def _dedupe_blocks(blocks: list[TextBlock]) -> list[TextBlock]:
    result: list[TextBlock] = []
    for block in sorted(blocks, key=lambda item: (item.page, item.bbox["top"], item.bbox["left"])):
        duplicate = any(
            item.page == block.page
            and _normal(item.text) == _normal(block.text)
            and abs(item.bbox["left"] - block.bbox["left"]) < 1
            and abs(item.bbox["top"] - block.bbox["top"]) < 1
            for item in result
        )
        if not duplicate:
            result.append(block)
    return result


def _same_row(left: TextBlock, right: TextBlock) -> bool:
    overlap = min(left.bbox["bottom"], right.bbox["bottom"]) - max(left.bbox["top"], right.bbox["top"])
    height = max(left.bbox["bottom"] - left.bbox["top"], right.bbox["bottom"] - right.bbox["top"], 1)
    return overlap / height >= 0.35 or abs((left.bbox["top"] + left.bbox["bottom"]) / 2 - (right.bbox["top"] + right.bbox["bottom"]) / 2) <= height * 0.8


def _looks_like_prose(value: str) -> bool:
    """Keep ordinary prose out of the ambiguous-field review queue."""

    value = value.strip()
    if len(value) > 100 or len(_tokens(value)) > 9:
        return True
    return bool(re.search(r"[.!?][\"')\]]*$", value))


def _unlabeled_item(block: TextBlock) -> dict[str, Any]:
    if block.label in {"title", "section_header"}:
        kind = block.label
    elif _looks_like_prose(block.text):
        kind = "paragraph"
    else:
        kind = "text"
    return {
        "kind": kind,
        "text": block.text,
        "page": block.page,
        "bbox": block.bbox,
        "reason": "Unlabeled source text",
        "source": {"kind": "coordinates", "page": block.page, "bbox": block.bbox, "label": block.label},
    }


def _coordinate_fields(blocks: list[TextBlock]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    fields: list[dict[str, Any]] = []
    consumed: set[int] = set()
    review_blocks: set[int] = set()
    for index, label in enumerate(blocks):
        if label.label in {"section_header", "title"} or not _label_candidate(label.text):
            continue
        candidates: list[tuple[float, int]] = []
        for value_index, value in enumerate(blocks):
            if value_index == index or value.label in {"section_header", "title"} or ":" in value.text or not _value_like(value.text) or value.page != label.page or value.bbox["left"] <= label.bbox["right"] or not _same_row(label, value):
                continue
            between = [item for item in blocks if item.page == label.page and label.bbox["right"] < item.bbox["left"] < value.bbox["left"] and _same_row(label, item)]
            if any(_label_candidate(item.text) for item in between):
                continue
            gap = value.bbox["left"] - label.bbox["right"]
            height = max(label.bbox["bottom"] - label.bbox["top"], value.bbox["bottom"] - value.bbox["top"], 1)
            if gap > max(30, height * 14):
                continue
            score = (0.45 if _value_like(value.text) else 0.2) + max(0.0, 0.3 - gap / max(1, height * 30))
            score += 0.25 if _same_row(label, value) else 0
            candidates.append((score, value_index))
        if not candidates:
            for value_index, value in enumerate(blocks):
                if value_index == index or value.label in {"section_header", "title"} or not _value_like(value.text) or value.page != label.page:
                    continue
                vertical_gap = value.bbox["top"] - label.bbox["bottom"]
                label_height = max(label.bbox["bottom"] - label.bbox["top"], 1)
                horizontal_overlap = min(label.bbox["right"], value.bbox["right"]) - max(label.bbox["left"], value.bbox["left"])
                if vertical_gap < 0 or vertical_gap > label_height * 8 or horizontal_overlap <= 0:
                    continue
                if any(
                    other_index not in {index, value_index}
                    and other.page == label.page
                    and _label_candidate(other.text)
                    and _same_row(other, value)
                    for other_index, other in enumerate(blocks)
                ):
                    continue
                between = [item for item in blocks if item.page == label.page and label.bbox["bottom"] < item.bbox["top"] < value.bbox["top"]]
                if any(_label_candidate(item.text) for item in between):
                    continue
                candidates.append((0.52 - vertical_gap / max(1, label_height * 30), value_index))
        if not candidates:
            if (
                label.label not in {"section_header", "title"}
                and len(_tokens(label.text)) >= 2
                and not _looks_like_prose(label.text)
            ):
                fields.append({"text": label.text, "page": label.page, "bbox": label.bbox, "reason": "No unique coordinate value"})
                review_blocks.add(index)
            continue
        candidates.sort(reverse=True)
        if len(candidates) > 1 and abs(candidates[0][0] - candidates[1][0]) < 0.08:
            fields.append({"text": label.text, "page": label.page, "bbox": label.bbox, "reason": "Competing coordinate values"})
            review_blocks.add(index)
            continue
        value_index = candidates[0][1]
        value = blocks[value_index]
        fields.append({
            "label": label.text,
            "value": value.text,
            "confidence": min(0.94, 0.73 + candidates[0][0] / 3),
            "evidence": ["coordinates"],
            "source": {"kind": "coordinates", "page": label.page, "bbox": label.bbox, "value_bbox": value.bbox},
        })
        consumed.update({index, value_index})
    return fields, [
        _unlabeled_item(block)
        for index, block in enumerate(blocks)
        if index not in consumed and index not in review_blocks
    ]


def _reconcile(markdown_fields: list[dict[str, Any]], coordinate_fields: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    used_coordinates: set[int] = set()
    for markdown_field in markdown_fields:
        matches = [
            (index, field)
            for index, field in enumerate(coordinate_fields)
            if index not in used_coordinates and "label" in field and _normal(field["label"]) == _normal(markdown_field["label"])
        ]
        exact = [pair for pair in matches if _normal(pair[1].get("value", "")) == _normal(markdown_field.get("value", ""))]
        if exact:
            index, field = exact[0]
            used_coordinates.add(index)
            merged = dict(markdown_field)
            merged["confidence"] = 0.98
            merged["evidence"] = ["markdown", "coordinates"]
            merged["source"] = {**markdown_field.get("source", {}), **field.get("source", {})}
            merged["status"] = "empty" if not merged.get("value") else "accepted"
            accepted.append(merged)
        elif matches:
            review.append({"label": markdown_field["label"], "markdown": markdown_field.get("value", ""), "coordinates": [field.get("value", "") for _, field in matches], "reason": "Markdown and coordinate evidence disagree", "source": markdown_field.get("source", {})})
        else:
            accepted.append({**markdown_field, "status": "empty" if not markdown_field.get("value") else "accepted"})
    accepted.extend(
        {
            **field,
            "status": "empty" if not field.get("value") else "accepted",
        }
        for index, field in enumerate(coordinate_fields)
        if index not in used_coordinates and "label" in field
    )
    review.extend(field for field in coordinate_fields if "text" in field)
    return accepted, review


def _field_pages(field: dict[str, Any]) -> list[int]:
    source = field.get("source") or {}
    pages = source.get("pages", []) if isinstance(source, dict) else []
    result = [page for page in pages if isinstance(page, int)] if isinstance(pages, list) else []
    page = source.get("page") if isinstance(source, dict) else None
    if isinstance(page, int):
        result.append(page)
    return sorted(set(result))


def _matches_mapped_field_source(text: str, fields: list[dict[str, Any]]) -> bool:
    normalized_text = _normal(text)
    if not normalized_text:
        return False
    for field in fields:
        label = _normal(str(field.get("label", "")))
        value = _normal(str(field.get("value", "")))
        if normalized_text == label or (value and normalized_text == value):
            return True
        if label and value and label in normalized_text and value in normalized_text:
            return True
    return False


def _dedupe_fields(fields: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Collapse exact repeated logical fields while preserving their pages."""

    deduped: list[dict[str, Any]] = []
    by_key: dict[tuple[str, str], int] = {}
    collapsed = 0
    for field in fields:
        label = str(field.get("label", "")).strip()
        if not label:
            deduped.append(field)
            continue
        key = (_normal(label), str(field.get("value", "")).strip())
        existing_index = by_key.get(key)
        if existing_index is None:
            first = dict(field)
            source = dict(first.get("source") or {})
            pages = _field_pages(first)
            if pages:
                source["pages"] = pages
            source["occurrences"] = 1
            first["source"] = source
            deduped.append(first)
            by_key[key] = len(deduped) - 1
            continue

        existing = deduped[existing_index]
        existing_source = dict(existing.get("source") or {})
        pages = sorted(set(_field_pages(existing) + _field_pages(field)))
        if pages:
            existing_source["pages"] = pages
        existing_source["occurrences"] = int(existing_source.get("occurrences", 1)) + 1
        existing["source"] = existing_source
        existing["confidence"] = max(existing.get("confidence", 0), field.get("confidence", 0))
        existing["evidence"] = list(dict.fromkeys(existing.get("evidence", []) + field.get("evidence", [])))
        collapsed += 1
    return deduped, collapsed


def _attach_block_pages(fields: list[dict[str, Any]], blocks: list[TextBlock]) -> None:
    pages_by_label: dict[str, set[int]] = {}
    for block in blocks:
        pages_by_label.setdefault(_normal(block.text), set()).add(block.page)
    for field in fields:
        label = _normal(str(field.get("label", "")))
        if not label:
            continue
        pages = sorted(set(_field_pages(field)) | pages_by_label.get(label, set()))
        if pages:
            source = dict(field.get("source") or {})
            source["pages"] = pages
            field["source"] = source


def _same_bbox(left: Any, right: Any, tolerance: float = 1.5) -> bool:
    if not isinstance(left, dict) or not isinstance(right, dict):
        return False
    return all(
        isinstance(left.get(key), (int, float))
        and isinstance(right.get(key), (int, float))
        and abs(left[key] - right[key]) <= tolerance
        for key in ("left", "top", "right", "bottom")
    )


def _merge_value_continuations(fields: list[dict[str, Any]], blocks: list[TextBlock]) -> tuple[list[dict[str, Any]], set[str]]:
    """Keep text directly below a mapped value with that same field."""

    value_sources = [
        (field, field.get("source") or {})
        for field in fields
        if isinstance(field.get("source"), dict) and field["source"].get("value_bbox")
    ]
    kept_fields: list[dict[str, Any]] = []
    removed_value_labels: set[str] = set()
    for field in fields:
        source = field.get("source") or {}
        is_value_relabel = any(
            other is not field
            and _normal(str(field.get("label", ""))) == _normal(str(other.get("value", "")))
            and _same_bbox(source.get("bbox"), other_source.get("value_bbox"))
            for other, other_source in value_sources
        )
        if is_value_relabel:
            removed_value_labels.add(_normal(str(field.get("label", ""))))
            continue
        kept_fields.append(field)

    protected_boxes = [
        box
        for field in kept_fields
        for box in ((field.get("source") or {}).get("bbox"), (field.get("source") or {}).get("value_bbox"))
        if box
    ]
    label_blocks_by_page: dict[int, list[TextBlock]] = {}
    for block in blocks:
        if ":" in block.text or block.label in {"section_header", "title"}:
            label_blocks_by_page.setdefault(block.page, []).append(block)
    continuation_texts: set[str] = set()
    for field in kept_fields:
        source = field.get("source") or {}
        value_bbox = source.get("value_bbox")
        page = source.get("page")
        if not isinstance(value_bbox, dict) or not isinstance(page, int) or not field.get("value"):
            continue
        value_height = max(value_bbox.get("bottom", 0) - value_bbox.get("top", 0), 1)
        last_bottom = value_bbox["bottom"]
        continuation: list[str] = []
        for block in blocks:
            if block.page != page or _same_bbox(block.bbox, value_bbox) or any(_same_bbox(block.bbox, box) for box in protected_boxes):
                continue
            if block.bbox["top"] < last_bottom - 1:
                continue
            if abs(block.bbox["left"] - value_bbox["left"]) > max(12, value_height * 2):
                continue
            horizontal_overlap = min(value_bbox["right"], block.bbox["right"]) - max(value_bbox["left"], block.bbox["left"])
            if horizontal_overlap <= 0:
                continue
            if any(
                other is not block
                and other.bbox["right"] < block.bbox["left"]
                and _same_row(other, block)
                for other in label_blocks_by_page.get(block.page, [])
            ):
                continue
            vertical_gap = block.bbox["top"] - last_bottom
            if vertical_gap > max(18, value_height * 3):
                if continuation:
                    break
                continue
            continuation.append(block.text)
            continuation_texts.add(_normal(block.text))
            last_bottom = block.bbox["bottom"]
            value_height = max(value_height, block.bbox["bottom"] - block.bbox["top"])
        if continuation:
            field["value"] = "\n".join([str(field["value"]), *continuation])
    return kept_fields, continuation_texts | removed_value_labels


def _table_output(table_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index, record in enumerate(table_records, start=1):
        table = record["table"]
        uncertain = any(
            cell and cell.get("status") == "uncertain"
            for row in table.get("cell_grid", [])
            for cell in row
        )
        output.append({
            "id": f"table-{index}",
            "name": f"Table {index}",
            "pages": table.get("pages", []),
            "duplicate_pages": table.get("duplicate_pages", []),
            "columns": table.get("columns", []),
            "row_count": table.get("row_count", len(table.get("grid_values", []))),
            "column_count": table.get("column_count", len(table.get("columns", []))),
            "header_rows": table.get("header_structure", []),
            "rows": table.get("rows", []),
            "grid": table.get("grid_values", []),
            "cells": table.get("cell_grid", []),
            "bbox": table.get("bbox"),
            "bboxes": table.get("bboxes", []),
            "confidence": 0.72 if uncertain else 0.97 if all(cell and cell.get("bbox") for row in table.get("cell_grid", []) for cell in row if cell and cell.get("status") == "value") else 0.8,
            "status": "review" if uncertain else "accepted",
        })
    return output


def extract_automatic(markdown: str, raw_document: dict[str, Any], table_records: list[dict[str, Any]], source_file: str) -> tuple[dict[str, Any], str]:
    """Map a parsed PDF without a schema or an LLM."""

    markdown_tables, _ = _markdown_tables(markdown)
    markdown_fields = _markdown_fields(markdown, markdown_tables)
    blocks = _text_blocks(raw_document, table_records)
    coordinate_fields, unlabeled = _coordinate_fields(blocks)
    fields, review = _reconcile(markdown_fields, coordinate_fields)
    _attach_block_pages(fields, blocks)
    fields, consumed_coordinate_texts = _merge_value_continuations(fields, blocks)
    fields, field_duplicates = _dedupe_fields(fields)
    accepted_labels = {_normal(str(field.get("label", ""))) for field in fields if field.get("label")}
    unlabeled = [
        item
        for item in unlabeled
        if _normal(str(item.get("text", ""))) not in accepted_labels
        and not _matches_mapped_field_source(str(item.get("text", "")), fields)
    ]
    review = [
        item
        for item in review
        if not (
            item.get("text")
            and (
                _normal(str(item["text"])) in (accepted_labels | consumed_coordinate_texts)
                or _matches_mapped_field_source(str(item["text"]), fields)
            )
        )
    ]
    tables = _table_output(table_records)
    table_duplicates = sum(len(table.get("duplicate_pages", [])) for table in tables)
    result = {
        "source_file": source_file,
        "mode": "automatic",
        "fields": fields,
        "tables": tables,
        "unlabeled": unlabeled,
        "review": review,
        "deduplication": {
            "identical_fields_collapsed": field_duplicates,
            "identical_table_copies_collapsed": table_duplicates,
        },
        "mapping": {"markdown": True, "coordinates": True, "llm": LLM_FALLBACK_ENABLED},
    }
    return result, automatic_csv(result)


def automatic_csv(result: dict[str, Any]) -> str:
    fields = result.get("fields", [])
    field_names: list[str] = []
    for field in fields:
        label = str(field.get("label", "Field")).strip() or "Field"
        candidate = label
        suffix = 2
        while candidate in field_names:
            candidate = f"{label} ({suffix})"
            suffix += 1
        field_names.append(candidate)
    table_columns: list[str] = []
    for table in result.get("tables", []):
        for column in table.get("columns", []):
            if column not in table_columns:
                table_columns.append(column)
    columns = ["source_file", *field_names, *table_columns, "unlabeled_content", "review_content"]
    rows: list[dict[str, str]] = []
    tables = result.get("tables", [])
    unlabeled_content = json.dumps(result.get("unlabeled", []), ensure_ascii=False, separators=(",", ":"))
    review_content = json.dumps(result.get("review", []), ensure_ascii=False, separators=(",", ":"))
    if tables:
        for table in tables:
            for table_row in table.get("rows", []):
                row = {column: "" for column in columns}
                row["source_file"] = str(result.get("source_file", ""))
                row["unlabeled_content"] = unlabeled_content
                row["review_content"] = review_content
                for index, field in enumerate(fields):
                    row[field_names[index]] = str(field.get("value", ""))
                for column in table_columns:
                    row[column] = str(table_row.get(column, ""))
                rows.append(row)
    else:
        row = {column: "" for column in columns}
        row["source_file"] = str(result.get("source_file", ""))
        row["unlabeled_content"] = unlabeled_content
        row["review_content"] = review_content
        for index, field in enumerate(fields):
            row[field_names[index]] = str(field.get("value", ""))
        rows.append(row)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="raise")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()
