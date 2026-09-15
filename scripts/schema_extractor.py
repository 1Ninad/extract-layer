#!/usr/bin/env python3
"""Call an LLM with a user-defined extraction schema and validate its output."""

from __future__ import annotations

import base64
import json
import os
import re
import string
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from extraction_schema import ExtractionSchema, FieldSpec


DEFAULT_MODEL = "mistralai/mistral-small-24b-instruct-2501"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MARKDOWN_CHUNK_CHAR_LIMIT = 50_000  # legacy helper constant; unused by the default runner


# These words are allowed as connective/label text around a source value. They
# help us project an LLM's natural-language answer back onto the source without
# allowing an arbitrary paraphrase to become an output value.
_SOURCE_WRAPPER_WORDS = frozenset(
    {
        "a",
        "an",
        "amount",
        "amounts",
        "and",
        "as",
        "at",
        "by",
        "date",
        "dated",
        "ended",
        "for",
        "from",
        "in",
        "is",
        "of",
        "on",
        "period",
        "periods",
        "shown",
        "table",
        "the",
        "to",
        "through",
        "value",
        "was",
        "with",
    }
)
_SOURCE_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def load_dotenv(path: Path) -> None:
    """Load simple KEY=VALUE entries without requiring python-dotenv."""

    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def json_schema(schema: ExtractionSchema) -> dict[str, Any]:
    """Build a strict response schema while keeping values source-faithful."""

    def field_schema(field: FieldSpec) -> dict[str, Any]:
        if field.type == "object":
            value_schema = _object_schema(field.fields, _field_description(field))
        elif field.type == "array":
            item_schema = (
                _object_schema(field.fields, "Nested object item")
                if field.item_type == "object"
                else {"type": "string"}
            )
            value_schema = {
                "type": "array",
                "items": item_schema,
                "description": _field_description(field),
            }
        else:
            # Number/date/boolean values stay strings so printed formatting is preserved.
            value_schema = {"type": "string", "description": _field_description(field)}
        return value_schema

    def _object_schema(fields: tuple[FieldSpec, ...], description: str) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {field.name: field_schema(field) for field in fields},
            "required": [field.name for field in fields],
            "additionalProperties": False,
            "description": description,
        }

    document_properties = {field.name: field_schema(field) for field in schema.fields}
    document_required = [field.name for field in schema.fields]
    properties: dict[str, Any] = {
        "fields": {
            "type": "object",
            "properties": document_properties,
            "required": document_required,
            "additionalProperties": False,
        }
    }
    required = ["fields"]

    if schema.records is not None:
        record_properties = {field.name: field_schema(field) for field in schema.records.fields}
        properties["records"] = {
            "type": "array",
            "description": schema.records.description,
            "items": {
                "type": "object",
                "properties": record_properties,
                "required": [field.name for field in schema.records.fields],
                "additionalProperties": False,
            },
        }
        required.append("records")

    return {
        "name": schema.name,
        "strict": True,
        "schema": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
    }


def _field_description(field: FieldSpec) -> str:
    type_hint = field.type
    if field.type == "array":
        type_hint += f" of {field.item_type} values"
    return f"Declared type: {type_hint}. {field.description} Leave empty when absent."


def prompt_messages(schema: ExtractionSchema, markdown: str) -> list[dict[str, str]]:
    system = _system_prompt(schema, f"SOURCE MARKDOWN:\n{markdown}", "Markdown")
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "Extract the configured fields from the source Markdown."},
    ]


def _system_prompt(schema: ExtractionSchema, source_instruction: str, source_kind: str) -> str:
    lines = [
        f"You extract values from a digitally-generated PDF represented as {source_kind}.",
        f"Use only values that appear in the supplied {source_kind}.",
        "Copy every returned value exactly as printed, preserving case, punctuation, spacing, leading zeroes, trailing zeroes, and date formatting.",
        "Do not translate, correct OCR, calculate, normalize, convert units, reformat dates, or infer unsupported values.",
        "Return an empty string for an absent scalar field and an empty array for an absent array field.",
        f"Every non-empty scalar or array item must be directly supported by the supplied {source_kind}.",
        "The declared type guides interpretation but does not change the printed value.",
        "",
        f"OVERALL DOCUMENT CONTEXT: {schema.description}",
        "",
        "DOCUMENT FIELDS:",
    ]
    lines.extend(_prompt_field(field) for field in schema.fields)
    if schema.records is not None:
        lines.extend(
            [
                "",
                f"REPEATED RECORD GROUP: {schema.records.name}",
                schema.records.description,
                "Return one record for each separately supported repeated item or table row.",
                "RECORD FIELDS:",
            ]
        )
        lines.extend(_prompt_field(field) for field in schema.records.fields)
    lines.extend(
        [
            "",
            "Return only the requested JSON object.",
            source_instruction,
        ]
    )
    return "\n".join(lines)


def _prompt_field(field: FieldSpec) -> str:
    type_hint = field.type if field.type != "array" else f"array of {field.item_type}"
    lines = [f"- {field.name} ({type_hint}): {field.description}"]
    for nested_field in field.fields:
        lines.extend(f"  {line}" for line in _prompt_field(nested_field))
    return "\n".join(lines)


def call_openrouter(
    markdown: str,
    schema: ExtractionSchema,
    api_key: str,
    model: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": prompt_messages(schema, markdown),
        "stream": False,
        "response_format": {"type": "json_schema", "json_schema": json_schema(schema)},
        "provider": {"require_parameters": True},
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
            "X-OpenRouter-Title": "Generic PDF schema extractor",
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


def extract_markdown(
    markdown: str,
    schema: ExtractionSchema,
    api_key: str,
    model: str,
    source_file: str,
) -> dict[str, Any]:
    """Extract from Markdown, splitting only when the model context is too small.

    The original PDF is deliberately never sent to the model.  A large
    document is divided at Markdown line/table boundaries, each response is
    validated against the complete local Markdown source, and the structured
    values are merged before output is written.
    """

    try:
        response = call_openrouter(markdown, schema, api_key, model)
        return normalize_response(response, markdown, schema, source_file)
    except RuntimeError as exc:
        if not (_is_context_limit_error(exc) or _is_truncated_response_error(exc)):
            raise
        print(
            "Markdown does not fit in one structured response; retrying with bounded Markdown chunks...",
            flush=True,
        )
    except ValueError as exc:
        if "exact source span" not in str(exc):
            raise
        print(
            "Markdown source validation failed; retrying with Markdown chunks...",
            flush=True,
        )

    chunks = split_markdown(markdown, MARKDOWN_CHUNK_CHAR_LIMIT)
    if len(chunks) < 2:
        raise RuntimeError("Markdown extraction failed and could not be split into multiple chunks")
    print(f"Extracting {len(chunks)} Markdown chunks...", flush=True)
    normalized_chunks: list[dict[str, Any]] = []
    pending = [(str(index), chunk) for index, chunk in enumerate(chunks, start=1)]
    while pending:
        label, chunk = pending.pop(0)
        print(f"  Markdown chunk {label}", flush=True)
        try:
            response = call_openrouter(chunk, schema, api_key, model)
        except RuntimeError as exc:
            if _is_context_limit_error(exc) and len(chunk) > 12_000:
                smaller_chunks = split_markdown(chunk, max_chars=max(12_000, len(chunk) // 2))
                if len(smaller_chunks) < 2:
                    raise
                print(f"  Chunk {label} still exceeds context; subdividing it", flush=True)
                pending = [
                    (f"{label}.{sub_index}", smaller_chunk)
                    for sub_index, smaller_chunk in enumerate(smaller_chunks, start=1)
                ] + pending
                continue
            if _is_truncated_response_error(exc) and schema.records is None and len(schema.fields) > 1:
                print(f"  Chunk {label} response was truncated; splitting the schema fields", flush=True)
                normalized_chunks.append(
                    _extract_field_groups(
                        chunk,
                        markdown,
                        schema,
                        api_key,
                        model,
                        source_file,
                    )
                )
                continue
            raise
        try:
            normalized_chunks.append(
                normalize_response(response, markdown, schema, source_file, validate_source=True)
            )
        except ValueError as exc:
            if "exact source span" not in str(exc):
                raise
            print(f"  Chunk {label} failed source validation; retrying strictly", flush=True)
            retry_response = call_openrouter(
                chunk,
                schema,
                api_key,
                model,
                retry_note=(
                    "The previous response contained a value that was not an exact source span. "
                    "Return an empty string or empty array item when the source does not visibly "
                    "contain the requested value. Do not repeat the rejected value. "
                    f"Validation detail: {exc}"
                ),
            )
            try:
                normalized_chunks.append(
                    normalize_response(retry_response, markdown, schema, source_file, validate_source=True)
                )
            except ValueError as retry_exc:
                if "exact source span" not in str(retry_exc):
                    raise
                print(f"  Chunk {label} still contains unsupported values; discarding them", flush=True)
                unsafe_result = normalize_response(
                    retry_response, markdown, schema, source_file, validate_source=False
                )
                normalized_chunks.append(_discard_unsupported_values(unsafe_result, schema, markdown))
    return merge_normalized_results(normalized_chunks, schema)


def _is_context_limit_error(error: RuntimeError) -> bool:
    message = str(error).lower()
    return (
        "maximum context length" in message
        or "context length" in message
        or "too many tokens" in message
        or "input too long" in message
        or "context_length_exceeded" in message
    )


def _is_truncated_response_error(error: RuntimeError) -> bool:
    message = str(error).lower()
    return "finish_reason" in message and "length" in message


def _extract_field_groups(
    chunk: str,
    full_markdown: str,
    schema: ExtractionSchema,
    api_key: str,
    model: str,
    source_file: str,
) -> dict[str, Any]:
    """Extract a large document schema in smaller response schemas."""

    fields = list(schema.fields)
    midpoint = max(1, len(fields) // 2)
    groups = [tuple(fields[:midpoint]), tuple(fields[midpoint:])]
    partial_results: list[dict[str, Any]] = []
    for group in groups:
        if not group:
            continue
        subset = ExtractionSchema(
            schema_version=schema.schema_version,
            name=schema.name,
            description=schema.description,
            output_mode="document",
            fields=group,
        )
        subset.validate()
        try:
            response = call_openrouter(chunk, subset, api_key, model)
        except RuntimeError as exc:
            if _is_truncated_response_error(exc) and len(group) > 1:
                partial_results.append(
                    _extract_field_groups(
                        chunk,
                        full_markdown,
                        ExtractionSchema(
                            schema_version=schema.schema_version,
                            name=schema.name,
                            description=schema.description,
                            output_mode="document",
                            fields=group,
                        ),
                        api_key,
                        model,
                        source_file,
                    )
                )
                continue
            raise
        normalized = _normalize_subset_with_source_safety(
            response,
            chunk,
            full_markdown,
            subset,
            api_key,
            model,
            source_file,
        )
        partial_results.append(_expand_partial_result(normalized, schema))
    return merge_normalized_results(partial_results, schema)


def _normalize_subset_with_source_safety(
    response: dict[str, Any],
    chunk: str,
    full_markdown: str,
    schema: ExtractionSchema,
    api_key: str,
    model: str,
    source_file: str,
) -> dict[str, Any]:
    try:
        return normalize_response(response, full_markdown, schema, source_file, validate_source=True)
    except ValueError as exc:
        if "exact source span" not in str(exc):
            raise
        retry_response = call_openrouter(
            chunk,
            schema,
            api_key,
            model,
            retry_note=(
                "The previous response included a shortened, inferred, or otherwise unsupported "
                "value. Return only an exact source span from the Markdown; otherwise return an "
                "empty string or empty array. Do not paraphrase or repeat the rejected value. "
                f"Validation detail: {exc}"
            ),
        )
        try:
            return normalize_response(retry_response, full_markdown, schema, source_file, validate_source=True)
        except ValueError as retry_exc:
            if "exact source span" not in str(retry_exc):
                raise
            unsafe_result = normalize_response(
                retry_response, full_markdown, schema, source_file, validate_source=False
            )
            return _discard_unsupported_values(unsafe_result, schema, full_markdown)


def _expand_partial_result(result: dict[str, Any], schema: ExtractionSchema) -> dict[str, Any]:
    return {
        "source_file": result["source_file"],
        "schema": result["schema"],
        "fields": {
            field.name: result["fields"].get(field.name, _empty_value(field))
            for field in schema.fields
        },
    }


def _empty_value(field: FieldSpec) -> Any:
    if field.type == "object":
        return {nested.name: _empty_value(nested) for nested in field.fields}
    if field.type == "array":
        return []
    return ""


def split_markdown(markdown: str, max_chars: int = MARKDOWN_CHUNK_CHAR_LIMIT) -> list[str]:
    """Split Markdown on line/table boundaries without splitting table rows."""

    if max_chars < 1:
        raise ValueError("max_chars must be positive")
    if len(markdown) <= max_chars:
        return [markdown]

    lines = markdown.splitlines(keepends=True)
    units: list[str] = []
    index = 0
    while index < len(lines):
        if lines[index].lstrip().startswith("|"):
            end = index + 1
            while end < len(lines) and lines[end].lstrip().startswith("|"):
                end += 1
            units.append("".join(lines[index:end]))
            index = end
        else:
            units.append(lines[index])
            index += 1

    chunks: list[str] = []
    current: list[str] = []
    current_size = 0
    for unit in units:
        if current and current_size + len(unit) > max_chars:
            chunks.append("".join(current))
            current = []
            current_size = 0
        if len(unit) <= max_chars:
            current.append(unit)
            current_size += len(unit)
            continue
        # A very long non-table line is unusual, but still split it safely.
        for start in range(0, len(unit), max_chars):
            part = unit[start : start + max_chars]
            if current:
                chunks.append("".join(current))
                current = []
                current_size = 0
            chunks.append(part)
    if current:
        chunks.append("".join(current))
    return chunks


def merge_normalized_results(
    results: list[dict[str, Any]],
    schema: ExtractionSchema,
) -> dict[str, Any]:
    if not results:
        raise ValueError("No Markdown extraction results were returned")
    merged: dict[str, Any] = {
        "source_file": results[0]["source_file"],
        "schema": results[0]["schema"],
        "fields": {},
    }
    for field in schema.fields:
        merged["fields"][field.name] = _merge_values(
            [result["fields"][field.name] for result in results], field, f"field {field.name!r}"
        )
    if schema.records is not None:
        merged_records: list[dict[str, Any]] = []
        seen: set[str] = set()
        for result in results:
            for record in result.get("records", []):
                key = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                if key not in seen:
                    seen.add(key)
                    merged_records.append(record)
        merged["records"] = merged_records
    return merged


def _merge_values(values: list[Any], field: FieldSpec, location: str) -> Any:
    if field.type == "object":
        return {
            nested.name: _merge_values(
                [value[nested.name] for value in values], nested, f"{location}.{nested.name}"
            )
            for nested in field.fields
        }
    if field.type == "array":
        if field.item_type == "object":
            merged_items: list[dict[str, Any]] = []
            seen: set[str] = set()
            for value in values:
                for item in value:
                    key = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                    if key not in seen:
                        seen.add(key)
                        merged_items.append(item)
            return merged_items
        merged_items: list[str] = []
        seen_items: set[str] = set()
        for value in values:
            for item in value:
                if item not in seen_items:
                    seen_items.add(item)
                    merged_items.append(item)
        return merged_items

    non_empty = [value for value in values if value]
    distinct = list(dict.fromkeys(non_empty))
    if len(distinct) > 1:
        raise ValueError(f"Conflicting non-empty values found while merging {location}: {distinct!r}")
    return distinct[0] if distinct else ""


def _discard_unsupported_values(
    result: dict[str, Any],
    schema: ExtractionSchema,
    markdown: str,
) -> dict[str, Any]:
    """Remove non-source values from a chunk after its strict retry failed."""

    filtered: dict[str, Any] = {
        "source_file": result["source_file"],
        "schema": result["schema"],
        "fields": {
            field.name: _filter_value(result["fields"][field.name], field, markdown)
            for field in schema.fields
        },
    }
    if schema.records is not None:
        filtered["records"] = [
            {
                field.name: _filter_value(record[field.name], field, markdown)
                for field in schema.records.fields
            }
            for record in result.get("records", [])
        ]
    return filtered


def _filter_value(value: Any, field: FieldSpec, markdown: str) -> Any:
    if field.type == "object":
        return {
            nested.name: _filter_value(value[nested.name], nested, markdown)
            for nested in field.fields
        }
    if field.type == "array":
        if field.item_type == "object":
            filtered_items: list[dict[str, Any]] = []
            for item in value:
                filtered_item = {
                    nested.name: _filter_value(item[nested.name], nested, markdown)
                    for nested in field.fields
                }
                if any(filtered_item.values()):
                    filtered_items.append(filtered_item)
            return filtered_items
        return [item for item in value if not item or has_exact_source_span(markdown, item)]
    if not value or has_exact_source_span(markdown, value):
        return value
    return ""


def call_openrouter_pdf(
    pdf_path: Path,
    schema: ExtractionSchema,
    api_key: str,
    model: str,
) -> dict[str, Any]:
    """Read the original PDF through OpenRouter's native PDF parser.

    This fallback is used when embedded PDF font mappings corrupt local text
    extraction while the rendered PDF remains readable.
    """

    encoded_pdf = base64.b64encode(pdf_path.read_bytes()).decode("ascii")
    messages = [
        {
            "role": "system",
            "content": _system_prompt(
                schema,
                "SOURCE PDF: The original PDF is attached to the user message. Read the rendered PDF directly.",
                "the attached PDF",
            ),
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Extract the configured fields from the attached PDF."},
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
        "response_format": {"type": "json_schema", "json_schema": json_schema(schema)},
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
            "HTTP-Referer": "https://openrouter.ai",
            "X-OpenRouter-Title": "Generic PDF schema extractor PDF fallback",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenRouter PDF fallback HTTP {exc.code}: {detail[:1500]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenRouter PDF fallback failed: {exc.reason}") from exc

    try:
        response_json = json.loads(body)
        content = response_json["choices"][0]["message"].get("content")
        parsed = json.loads(content)
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Invalid structured response from OpenRouter PDF fallback: {body[:1500]}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("OpenRouter PDF fallback response JSON must be an object")
    return parsed


def normalize_response(
    response: dict[str, Any],
    markdown: str,
    schema: ExtractionSchema,
    source_file: str,
    validate_source: bool = True,
) -> dict[str, Any]:
    if not isinstance(response, dict):
        raise ValueError("LLM response must be an object")
    raw_fields = response.get("fields")
    if not isinstance(raw_fields, dict):
        raise ValueError("LLM response must contain a fields object")
    _validate_keys(raw_fields, schema.fields, "document fields")
    fields = _normalize_fields(raw_fields, schema.fields, markdown, "document", validate_source)

    result: dict[str, Any] = {
        "source_file": source_file,
        "schema": schema.name,
        "fields": fields,
    }
    if schema.records is not None:
        raw_records = response.get("records")
        if not isinstance(raw_records, list):
            raise ValueError("LLM response must contain a records array")
        records: list[dict[str, Any]] = []
        for index, raw_record in enumerate(raw_records, start=1):
            if not isinstance(raw_record, dict):
                raise ValueError(f"LLM record {index} must be an object")
            _validate_keys(raw_record, schema.records.fields, f"record {index}")
            records.append(
                _normalize_fields(raw_record, schema.records.fields, markdown, f"record {index}", validate_source)
            )
        result["records"] = records
    return result


def _validate_keys(values: dict[str, Any], fields: tuple[FieldSpec, ...], location: str) -> None:
    expected = {field.name for field in fields}
    actual = set(values)
    missing = expected - actual
    unexpected = actual - expected
    if missing or unexpected:
        raise ValueError(
            f"LLM {location} schema mismatch; missing={sorted(missing)}, unexpected={sorted(unexpected)}"
        )


def _normalize_fields(
    values: dict[str, Any],
    fields: tuple[FieldSpec, ...],
    markdown: str,
    location: str,
    validate_source: bool,
) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for field in fields:
        value = values[field.name]
        normalized[field.name] = _normalize_value(value, field, markdown, f"{location} field {field.name!r}", validate_source)
    return normalized


def _normalize_value(
    value: Any,
    field: FieldSpec,
    markdown: str,
    location: str,
    validate_source: bool,
) -> Any:
    if field.type == "object":
        if not isinstance(value, dict):
            raise ValueError(f"LLM {location} must be an object")
        _validate_keys(value, field.fields, location)
        return _normalize_fields(value, field.fields, markdown, location, validate_source)

    if field.type == "array":
        if not isinstance(value, list):
            raise ValueError(f"LLM {location} must be an array")
        if field.item_type == "object":
            normalized_objects: list[dict[str, Any]] = []
            for index, item in enumerate(value, start=1):
                if not isinstance(item, dict):
                    raise ValueError(f"LLM {location} item {index} must be an object")
                _validate_keys(item, field.fields, f"{location} item {index}")
                normalized_objects.append(
                    _normalize_fields(item, field.fields, markdown, f"{location} item {index}", validate_source)
                )
            return normalized_objects
        if not all(isinstance(item, str) for item in value):
            raise ValueError(f"LLM {location} must be an array of strings")
        if validate_source:
            return [
                _project_source_value(markdown, item, location)
                for item in value
            ]
        return value

    if not isinstance(value, str):
        raise ValueError(f"LLM {location} must be a string")
    if validate_source:
        return _project_source_value(markdown, value, location)
    return value


def _project_source_value(source: str, value: str, location: str) -> str:
    """Return a source-faithful value, using the LLM value only as a locator.

    The model commonly adds harmless connective words, for example ``as of``
    before a date. Exact values are kept unchanged. When exact matching fails,
    a conservative token match finds a source span whose meaningful tokens and
    numeric tokens are represented by the model value. The returned string is
    always sliced from ``source``; the model's spelling is never written out.
    """

    if not value:
        return value
    exact_span = _find_exact_source_span(source, value)
    if exact_span is not None:
        return source[exact_span[0] : exact_span[1]]

    projected = project_source_value(source, value)
    if projected is None:
        raise ValueError(
            f"LLM {location} could not be projected to an exact source span "
            f"in the Markdown: {value!r}"
        )
    return projected


def project_source_value(source: str, value: str) -> str | None:
    """Project a model candidate onto a unique, source-owned text span.

    This is deliberately conservative. It tolerates case, whitespace, and
    punctuation differences, a small set of connective words, and omitted
    non-numeric words inside a source span. It does not tolerate changed,
    missing, or extra numeric tokens.
    """

    source_tokens = _source_tokens(source)
    model_tokens = _normalized_tokens(value)
    if not source_tokens or not model_tokens:
        return None

    model_numeric = [token for token in model_tokens if _contains_digit(token)]
    substantive_model_tokens = [
        token for token in model_tokens if token not in _SOURCE_WRAPPER_WORDS
    ]
    if not substantive_model_tokens:
        return None

    candidates: dict[str, tuple[int, int]] = {}
    for source_index, source_token in enumerate(source_tokens):
        if source_token[0] != substantive_model_tokens[0]:
            continue

        # The model may omit descriptive words from a source value. Find all
        # ordered source-token matches, then return the complete source span.
        states: list[list[tuple[str, int, int]]] = [[source_token]]
        for model_token in substantive_model_tokens[1:]:
            next_states: list[list[tuple[str, int, int]]] = []
            for state in states:
                previous_end = state[-1][2]
                for candidate_token in source_tokens:
                    if candidate_token[1] >= previous_end and candidate_token[0] == model_token:
                        next_states.append([*state, candidate_token])
            states = next_states
            if not states:
                break

        for matched_tokens in states:
            start = matched_tokens[0][1]
            end = matched_tokens[-1][2]
            start, end = _expand_value_punctuation(source, start, end)
            candidate_text = source[start:end]
            candidate_tokens = _source_tokens(candidate_text)
            candidate_values = [token[0] for token in candidate_tokens]
            candidate_alnum_count = len(candidate_values)
            if candidate_alnum_count < 2 and not any(
                _contains_digit(token) for token in candidate_values
            ):
                continue
            if [token for token in candidate_values if _contains_digit(token)] != model_numeric:
                continue
            if _numeric_polarity(candidate_text) != _numeric_polarity(value):
                continue

            # Prefer the smallest source span that explains all substantive
            # model tokens. This strips labels while preserving source text.
            rank = (-candidate_alnum_count, 0)
            previous = candidates.get(candidate_text)
            if previous is None or rank > previous:
                candidates[candidate_text] = rank

    if not candidates:
        return None

    best_rank = max(candidates.values())
    best_values = [text for text, rank in candidates.items() if rank == best_rank]
    if len(best_values) != 1:
        return None
    return best_values[0]


def _source_tokens(source: str) -> list[tuple[str, int, int]]:
    # Normalize only token values for matching. Keep offsets in the original
    # string because the returned value is sliced from the original source.
    return [
        (unicodedata.normalize("NFKC", match.group()).casefold(), match.start(), match.end())
        for match in _SOURCE_TOKEN_RE.finditer(source)
    ]


def _normalized_tokens(value: str) -> list[str]:
    return [
        unicodedata.normalize("NFKC", match.group()).casefold()
        for match in _SOURCE_TOKEN_RE.finditer(value)
    ]


def _expand_value_punctuation(source: str, start: int, end: int) -> tuple[int, int]:
    """Include punctuation attached to a printed value, but not Markdown markup."""

    original_start = start
    while start > 0 and source[start - 1] in "$€£¥-+(":
        start -= 1
    trailing = "%,"
    if start < original_start and "(" in source[start:original_start]:
        trailing += ")"
    while end < len(source) and source[end] in trailing:
        end += 1
    return start, end


def _contains_digit(value: str) -> bool:
    return any(character in string.digits for character in value)


def _numeric_polarity(value: str) -> int:
    """Return positive/negative polarity for a printed numeric value."""

    if not _contains_digit(value):
        return 0
    compact = re.sub(r"\s+", "", value)
    if re.search(r"-\d", compact) or re.search(r"\([^()]*\d[^()]*\)", compact):
        return -1
    return 1


def _unmatched_tokens(model_tokens: list[str], candidate_tokens: list[str]) -> list[str]:
    remaining = list(candidate_tokens)
    unmatched: list[str] = []
    for token in model_tokens:
        if token in remaining:
            remaining.remove(token)
        else:
            unmatched.append(token)
    return unmatched


def has_exact_source_span(source: str, value: str) -> bool:
    """Reject a numeric value that is only a truncated part of a source token."""

    return _find_exact_source_span(source, value) is not None


def _find_exact_source_span(source: str, value: str) -> tuple[int, int] | None:
    """Find an exact source occurrence that is not inside a larger number."""

    start = 0
    while True:
        position = source.find(value, start)
        if position < 0:
            return None
        end = position + len(value)
        previous = source[position - 1] if position else ""
        following = source[end] if end < len(source) else ""
        numeric_value = any(character.isdigit() for character in value)
        adjacent_digit = (bool(previous) and previous in string.digits) or (
            bool(following) and following in string.digits
        )
        if not numeric_value or not adjacent_digit:
            return position, end
        start = position + 1


def csv_rows(result: dict[str, Any], schema: ExtractionSchema) -> tuple[list[str], list[dict[str, str]]]:
    """Flatten a canonical result into deterministic, one-row-per-record CSV data."""

    document_fields = [field.name for field in schema.fields]
    record_fields = [field.name for field in schema.records.fields] if schema.records else []
    columns = ["source_file", *document_fields, *record_fields]
    document_values = result["fields"]
    raw_records = result.get("records")
    if schema.records is None:
        raw_records = [None]
    elif not raw_records:
        raw_records = [None]

    rows: list[dict[str, str]] = []
    for record in raw_records:
        row = {"source_file": str(result["source_file"])}
        for field in schema.fields:
            row[field.name] = _csv_value(document_values[field.name])
        for field in schema.records.fields if schema.records else ():
            row[field.name] = _csv_value(record[field.name] if record else ([] if field.type == "array" else ""))
        rows.append(row)
    return columns, rows


def _csv_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)
