#!/usr/bin/env python3
"""Human-authored TOML schemas for generic PDF extraction."""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable


FIELD_TYPES = {"text", "number", "date", "boolean", "array", "object"}
SCALAR_TYPES = {"text", "number", "date", "boolean"}
NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
RESERVED_NAMES = {"source_file", "schema", "fields", "records"}


@dataclass(frozen=True)
class FieldSpec:
    name: str
    type: str
    description: str
    item_type: str = "text"
    fields: tuple["FieldSpec", ...] = ()

    def validate(self, location: str) -> None:
        if not NAME_PATTERN.fullmatch(self.name):
            raise ValueError(
                f"{location} field name {self.name!r} must contain only letters, numbers, and underscores, "
                "and must not start with a number"
            )
        if self.name in RESERVED_NAMES:
            raise ValueError(f"{location} field name {self.name!r} is reserved")
        if self.type not in FIELD_TYPES:
            raise ValueError(
                f"{location} field {self.name!r} has unsupported type {self.type!r}; "
                f"choose one of {sorted(FIELD_TYPES)}"
            )
        if not self.description.strip():
            raise ValueError(f"{location} field {self.name!r} needs a non-empty description")
        if self.type == "object":
            if not self.fields:
                raise ValueError(f"{location} object field {self.name!r} must define nested fields")
            _validate_unique_fields(self.fields, f"{location}.{self.name}")
        elif self.type == "array" and self.item_type not in SCALAR_TYPES | {"object"}:
            raise ValueError(
                f"{location} array field {self.name!r} has unsupported item_type {self.item_type!r}; "
                f"choose one of {sorted(SCALAR_TYPES | {'object'})}"
            )
        elif self.type != "array" and self.fields:
            raise ValueError(f"{location} scalar field {self.name!r} cannot define nested fields")
        if self.type == "array" and self.item_type == "object":
            if not self.fields:
                raise ValueError(f"{location} array field {self.name!r} must define nested object fields")
            _validate_unique_fields(self.fields, f"{location}.{self.name}[]")


@dataclass(frozen=True)
class RecordSpec:
    name: str
    description: str
    fields: tuple[FieldSpec, ...]

    def validate(self) -> None:
        if not NAME_PATTERN.fullmatch(self.name):
            raise ValueError("records.name must contain only letters, numbers, and underscores")
        if self.name in RESERVED_NAMES:
            raise ValueError(f"records.name {self.name!r} is reserved")
        if not self.description.strip():
            raise ValueError("records.description must not be empty")
        _validate_unique_fields(self.fields, "records")
        if not self.fields:
            raise ValueError("records must define at least one field")


@dataclass(frozen=True)
class ExtractionSchema:
    schema_version: int
    name: str
    description: str
    output_mode: str
    fields: tuple[FieldSpec, ...]
    records: RecordSpec | None = None

    def validate(self) -> None:
        if self.schema_version != 1:
            raise ValueError(f"schema_version must be 1, got {self.schema_version!r}")
        if not self.name.strip():
            raise ValueError("schema name must not be empty")
        if not self.description.strip():
            raise ValueError("schema description must not be empty")
        if self.output_mode not in {"document", "records"}:
            raise ValueError("output_mode must be 'document' or 'records'")
        _validate_unique_fields(self.fields, "document")
        if self.output_mode == "records" and self.records is None:
            raise ValueError("output_mode='records' requires a [records] section")
        if self.output_mode == "document" and self.records is not None:
            raise ValueError("output_mode='document' cannot include a [records] section")
        if self.records is not None:
            self.records.validate()
            document_names = {field.name for field in self.fields}
            record_names = {field.name for field in self.records.fields}
            overlap = document_names & record_names
            if overlap:
                raise ValueError(
                    "document and record fields must have unique names; duplicated: "
                    + ", ".join(sorted(overlap))
                )
        if not self.fields and not (self.records and self.records.fields):
            raise ValueError("schema must define at least one field")

    @property
    def all_fields(self) -> tuple[FieldSpec, ...]:
        record_fields = self.records.fields if self.records else ()
        return self.fields + record_fields

    @classmethod
    def from_toml(cls, path: Path) -> "ExtractionSchema":
        try:
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ValueError(f"Schema file not found: {path}") from exc
        except tomllib.TOMLDecodeError as exc:
            raise ValueError(f"Invalid TOML schema {path}: {exc}") from exc
        schema = cls.from_mapping(raw)
        schema.validate()
        return schema

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "ExtractionSchema":
        if not isinstance(raw, dict):
            raise ValueError("schema must be a TOML table")

        fields = tuple(_field_from_mapping(value, "document") for value in raw.get("fields", []))
        raw_records = raw.get("records")
        records = None
        if raw_records is not None:
            if not isinstance(raw_records, dict):
                raise ValueError("records must be a TOML table")
            records = RecordSpec(
                name=_string_value(raw_records, "name", "records"),
                description=_string_value(raw_records, "description", "records"),
                fields=tuple(
                    _field_from_mapping(value, "records") for value in raw_records.get("fields", [])
                ),
            )

        schema = cls(
            schema_version=_integer_value(raw, "schema_version", "schema"),
            name=_string_value(raw, "name", "schema"),
            description=_string_value(raw, "description", "schema"),
            output_mode=_string_value(raw, "output_mode", "schema"),
            fields=fields,
            records=records,
        )
        schema.validate()
        return schema


def _string_value(mapping: dict[str, Any], key: str, location: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{location}.{key} must be a string")
    return value


def _integer_value(mapping: dict[str, Any], key: str, location: str) -> int:
    value = mapping.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{location}.{key} must be an integer")
    return value


def _field_from_mapping(value: Any, location: str) -> FieldSpec:
    if not isinstance(value, dict):
        raise ValueError(f"{location} fields must be TOML tables")
    name = _string_value(value, "name", location)
    field_type = _string_value(value, "type", f"{location}.{name}")
    description = _string_value(value, "description", f"{location}.{name}")
    item_type = value.get("item_type", "text")
    if not isinstance(item_type, str):
        raise ValueError(f"{location}.{name}.item_type must be a string")
    nested_table = value.get("object")
    if nested_table is not None and not isinstance(nested_table, dict):
        raise ValueError(f"{location}.{name}.object must be a TOML table")
    nested_values = nested_table.get("fields", []) if nested_table is not None else value.get("fields", [])
    nested_fields = tuple(
        _field_from_mapping(child, f"{location}.{name}") for child in nested_values
    )
    return FieldSpec(name, field_type, description, item_type, nested_fields)


def _validate_unique_fields(fields: Iterable[FieldSpec], location: str) -> None:
    seen: set[str] = set()
    for field in fields:
        field.validate(location)
        if field.name in seen:
            raise ValueError(f"duplicate {location} field name: {field.name!r}")
        seen.add(field.name)


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def write_toml(schema: ExtractionSchema, path: Path) -> None:
    """Write a stable, human-readable representation of a validated schema."""

    schema.validate()
    lines = [
        f"schema_version = {schema.schema_version}",
        f"name = {_toml_string(schema.name)}",
        f"description = {_toml_string(schema.description)}",
        f"output_mode = {_toml_string(schema.output_mode)}",
        "",
    ]
    for field in schema.fields:
        lines.extend(_field_toml(field, "fields"))
    if schema.records is not None:
        lines.extend(
            [
                "[records]",
                f"name = {_toml_string(schema.records.name)}",
                f"description = {_toml_string(schema.records.description)}",
                "",
            ]
        )
        for field in schema.records.fields:
            lines.extend(_field_toml(field, "records.fields"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _field_toml(field: FieldSpec, array_key: str) -> list[str]:
    lines = [f"[[{array_key}]]", f"name = {_toml_string(field.name)}", f"type = {_toml_string(field.type)}"]
    if field.type == "array":
        lines.append(f"item_type = {_toml_string(field.item_type)}")
    lines.extend([f"description = {_toml_string(field.description)}", ""])
    if field.type == "object" or (field.type == "array" and field.item_type == "object"):
        lines.append(f"[{array_key}.object]")
        lines.append("")
        for nested_field in field.fields:
            lines.extend(_field_toml(nested_field, f"{array_key}.object.fields"))
    return lines


def create_schema_interactively(
    path: Path,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> ExtractionSchema:
    """Collect a schema without requiring the user to author TOML manually."""

    output_fn("Create a PDF extraction schema. Press Ctrl-C to cancel.")
    name = _ask_nonempty("Schema name: ", input_fn)
    description = _ask_nonempty("Overall document description: ", input_fn)
    output_mode = _ask_choice("Output mode [document/records] (document): ", {"document", "records"}, input_fn, "document")
    fields = _ask_fields("document", input_fn, output_fn, require_one=output_mode == "document")
    records = None
    if output_mode == "records":
        record_name = _ask_nonempty("Record group name: ", input_fn)
        record_description = _ask_nonempty("Record group description: ", input_fn)
        record_fields = _ask_fields("record", input_fn, output_fn, require_one=True)
        records = RecordSpec(record_name, record_description, tuple(record_fields))

    schema = ExtractionSchema(1, name, description, output_mode, tuple(fields), records)
    schema.validate()
    if path.exists():
        raise ValueError(f"Refusing to overwrite existing schema: {path}")
    write_toml(schema, path)
    output_fn(f"Wrote schema to {path}")
    return schema


def _ask_nonempty(prompt: str, input_fn: Callable[[str], str]) -> str:
    while True:
        value = input_fn(prompt).strip()
        if value:
            return value
        print("A value is required.")


def _ask_choice(
    prompt: str,
    choices: set[str],
    input_fn: Callable[[str], str],
    default: str,
) -> str:
    while True:
        value = input_fn(prompt).strip().lower() or default
        if value in choices:
            return value
        print(f"Choose one of: {', '.join(sorted(choices))}")


def _ask_fields(
    kind: str,
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
    require_one: bool = False,
) -> list[FieldSpec]:
    fields: list[FieldSpec] = []
    existing: set[str] = set()
    while True:
        if fields or not require_one:
            answer = input_fn(f"Add a {kind} field? [y/N]: ").strip().lower()
            if answer not in {"y", "yes"}:
                break
        name = _ask_nonempty("  Field name: ", input_fn)
        if name in existing:
            output_fn(f"  Field {name!r} already exists.")
            continue
        field_type = _ask_choice(
            "  Type [text/number/date/boolean/array/object] (text): ",
            FIELD_TYPES,
            input_fn,
            "text",
        )
        item_type = "text"
        nested_fields: list[FieldSpec] = []
        if field_type == "object":
            output_fn("  Define nested object fields:")
            nested_fields = _ask_fields(f"nested {name}", input_fn, output_fn, require_one=True)
        if field_type == "array":
            item_type = _ask_choice(
                "  Array item type [text/number/date/boolean/object] (text): ",
                SCALAR_TYPES | {"object"},
                input_fn,
                "text",
            )
            if item_type == "object":
                output_fn("  Define nested object fields:")
                nested_fields = _ask_fields(f"nested {name}", input_fn, output_fn, require_one=True)
        field_description = _ask_nonempty("  Field description: ", input_fn)
        fields.append(FieldSpec(name, field_type, field_description, item_type, tuple(nested_fields)))
        existing.add(name)
    return fields
