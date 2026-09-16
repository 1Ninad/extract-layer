from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

from backend.extraction_schema import ExtractionSchema, FieldSpec, RecordSpec, write_toml
from backend.automatic_extraction import TextBlock, _coordinate_fields, extract_automatic
from backend.hybrid_pdf_to_md import merge_markdown
from backend.run_pdf_to_outputs import extract_result, select_pdf, write_outputs
from backend.schema_extractor import (
    candidate_prompt_messages,
    compact_candidate_evidence,
    csv_rows,
    has_exact_source_span,
    json_schema,
    normalize_response,
    prompt_messages,
    project_source_value,
)


def document_schema() -> ExtractionSchema:
    return ExtractionSchema(
        schema_version=1,
        name="invoice",
        description="Extract invoice details.",
        output_mode="document",
        fields=(
            FieldSpec("invoice_number", "text", "The printed invoice identifier."),
            FieldSpec("invoice_date", "date", "The printed invoice date."),
            FieldSpec("tags", "array", "All printed tags.", "text"),
        ),
    )


def record_schema() -> ExtractionSchema:
    return ExtractionSchema(
        schema_version=1,
        name="invoice",
        description="Extract invoice details and lines.",
        output_mode="records",
        fields=(FieldSpec("invoice_number", "text", "The printed invoice identifier."),),
        records=RecordSpec(
            "line_items",
            "One record per line.",
            (
                FieldSpec("description", "text", "The line description."),
                FieldSpec("quantity", "number", "The printed line quantity."),
            ),
        ),
    )


def nested_schema() -> ExtractionSchema:
    return ExtractionSchema(
        schema_version=1,
        name="fund",
        description="Extract fund tables.",
        output_mode="document",
        fields=(
            FieldSpec(
                "average_annual_returns",
                "object",
                "The average annual returns table.",
                fields=(
                    FieldSpec("as_of_date", "text", "The table date."),
                    FieldSpec(
                        "periods",
                        "array",
                        "One object per period.",
                        "object",
                        (
                            FieldSpec("period_label", "text", "The period label."),
                            FieldSpec("return_before_taxes", "number", "The printed return."),
                        ),
                    ),
                ),
            ),
        ),
    )


class SchemaTests(unittest.TestCase):
    def test_simple_json_shape_infers_records_and_defaults_text_type(self) -> None:
        schema = ExtractionSchema.from_mapping(
            {
                "schema_version": 1,
                "name": "invoice",
                "description": "Extract invoice details.",
                "fields": [{"name": "invoice_number", "description": "The invoice number."}],
                "table": {
                    "name": "line_items",
                    "description": "Each line item.",
                    "fields": [{"name": "description", "description": "The line description."}],
                },
            }
        )
        self.assertEqual("records", schema.output_mode)
        self.assertEqual("text", schema.fields[0].type)
        self.assertEqual("line_items", schema.records.name)

    def test_toml_round_trip(self) -> None:
        schema = record_schema()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invoice.toml"
            write_toml(schema, path)
            loaded = ExtractionSchema.from_toml(path)
        self.assertEqual(loaded, schema)

    def test_nested_object_and_array_round_trip(self) -> None:
        schema = nested_schema()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fund.toml"
            write_toml(schema, path)
            loaded = ExtractionSchema.from_toml(path)
        self.assertEqual(loaded, schema)

    def test_duplicate_fields_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate document field"):
            ExtractionSchema.from_mapping(
                {
                    "schema_version": 1,
                    "name": "bad",
                    "description": "A schema.",
                    "output_mode": "document",
                    "fields": [
                        {"name": "value", "type": "text", "description": "First."},
                        {"name": "value", "type": "text", "description": "Second."},
                    ],
                }
            )

    def test_invalid_type_and_description_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported type"):
            ExtractionSchema.from_mapping(
                {
                    "schema_version": 1,
                    "name": "bad",
                    "description": "A schema.",
                    "output_mode": "document",
                    "fields": [{"name": "value", "type": "currency", "description": "Value."}],
                }
            )

    def test_records_mode_requires_record_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "records must define at least one field"):
            ExtractionSchema.from_mapping(
                {
                    "schema_version": 1,
                    "name": "bad",
                    "description": "A schema.",
                    "output_mode": "records",
                    "fields": [],
                    "records": {"name": "items", "description": "Rows.", "fields": []},
                }
            )
        with self.assertRaisesRegex(ValueError, "non-empty description"):
            ExtractionSchema.from_mapping(
                {
                    "schema_version": 1,
                    "name": "bad",
                    "description": "A schema.",
                    "output_mode": "document",
                    "fields": [{"name": "value", "type": "text", "description": ""}],
                }
            )


class ExtractionTests(unittest.TestCase):
    @staticmethod
    def _block(text: str, label: str = "text", top: float = 10) -> TextBlock:
        return TextBlock(
            text,
            1,
            {"left": 10, "top": top, "right": 500, "bottom": top + 14},
            label,
            "test",
        )

    def test_unpaired_prose_is_preserved_as_unlabeled_content(self) -> None:
        fields, unlabeled = _coordinate_fields(
            [self._block("This is an explanatory paragraph.")]
        )
        self.assertEqual(fields, [])
        self.assertEqual(unlabeled[0]["kind"], "paragraph")
        self.assertEqual(unlabeled[0]["text"], "This is an explanatory paragraph.")

    def test_long_unpaired_prose_is_not_dropped(self) -> None:
        paragraph = "This paragraph contains enough ordinary words to exceed the compact field candidate limit and must remain available to the caller."
        fields, unlabeled = _coordinate_fields([self._block(paragraph)])
        self.assertEqual(fields, [])
        self.assertEqual(unlabeled[0]["text"], paragraph)

    def test_ambiguous_compact_text_remains_in_review(self) -> None:
        fields, unlabeled = _coordinate_fields([self._block("Customer United States")])
        self.assertEqual(unlabeled, [])
        self.assertEqual(fields[0]["text"], "Customer United States")

    def test_automatic_output_preserves_unlabeled_and_review_content(self) -> None:
        paragraph = "This is an explanatory paragraph."
        result, csv_content = extract_automatic(
            paragraph + "\nCustomer United States\n",
            {
                "pages": {"1": {"page_no": 1, "size": {"width": 600, "height": 800}}},
                "texts": [
                    {
                        "text": paragraph,
                        "label": "text",
                        "prov": [{"page_no": 1, "bbox": {"l": 10, "r": 500, "t": 10, "b": 24}}],
                    },
                    {
                        "text": "Customer United States",
                        "label": "text",
                        "prov": [{"page_no": 1, "bbox": {"l": 10, "r": 220, "t": 40, "b": 54}}],
                    },
                ],
            },
            [],
            "example.pdf",
        )
        self.assertEqual(result["unlabeled"][0]["text"], paragraph)
        self.assertEqual(result["review"][0]["text"], "Customer United States")
        self.assertIn("unlabeled_content", csv_content.splitlines()[0])
        self.assertIn(paragraph, csv_content)

    def test_mapped_markdown_line_is_not_repeated_as_unlabeled_content(self) -> None:
        result, _ = extract_automatic(
            "Invoice No: INV-42\n",
            {
                "pages": {"1": {"page_no": 1, "size": {"width": 600, "height": 800}}},
                "texts": [
                    {
                        "text": "Invoice No: INV-42",
                        "label": "text",
                        "prov": [{"page_no": 1, "bbox": {"l": 10, "r": 220, "t": 10, "b": 24}}],
                    }
                ],
            },
            [],
            "example.pdf",
        )
        self.assertEqual(result["fields"][0]["value"], "INV-42")
        self.assertEqual(result["unlabeled"], [])
        self.assertEqual(result["review"], [])

    def test_dynamic_json_schema_contains_configured_fields_and_records(self) -> None:
        generated = json_schema(record_schema())["schema"]
        self.assertEqual(generated["required"], ["fields", "records"])
        self.assertIn("invoice_number", generated["properties"]["fields"]["properties"])
        self.assertIn("quantity", generated["properties"]["records"]["items"]["properties"])
        self.assertEqual(generated["properties"]["records"]["items"]["required"], ["description", "quantity"])

    def test_human_readable_field_names_are_preserved_in_schema_and_output(self) -> None:
        schema = ExtractionSchema.from_mapping(
            {
                "schema_version": 1,
                "name": "patient_report",
                "description": "Extract patient details.",
                "output_mode": "document",
                "fields": [{"name": "Date of Birth", "type": "text", "description": "Printed date."}],
            }
        )
        generated = json_schema(schema)["schema"]
        self.assertIn("Date of Birth", generated["properties"]["fields"]["properties"])
        result = normalize_response(
            {"fields": {"Date of Birth": "01/01/1970"}},
            "Date of Birth: 01/01/1970",
            schema,
            "patient.pdf",
        )
        self.assertEqual("01/01/1970", result["fields"]["Date of Birth"])
        columns, rows = csv_rows(result, schema)
        self.assertIn("Date of Birth", columns)
        self.assertEqual("01/01/1970", rows[0]["Date of Birth"])

    def test_dynamic_json_schema_contains_nested_table_shape(self) -> None:
        generated = json_schema(nested_schema())["schema"]["properties"]["fields"]["properties"]
        table = generated["average_annual_returns"]
        self.assertEqual(table["type"], "object")
        periods = table["properties"]["periods"]
        self.assertEqual(periods["items"]["type"], "object")
        self.assertEqual(periods["items"]["required"], ["period_label", "return_before_taxes"])

    def test_normalize_nested_table_and_serialize_it_in_csv(self) -> None:
        markdown = "Average Annual Total Returns\nDecember 31, 2024\n1 Year\n25.58%"
        response = {
            "fields": {
                "average_annual_returns": {
                    "as_of_date": "December 31, 2024",
                    "periods": [{"period_label": "1 Year", "return_before_taxes": "25.58%"}],
                }
            }
        }
        result = normalize_response(response, markdown, nested_schema(), "fund.pdf")
        self.assertEqual(
            result["fields"]["average_annual_returns"]["periods"][0]["return_before_taxes"],
            "25.58%",
        )
        _, rows = csv_rows(result, nested_schema())
        self.assertIn('"period_label":"1 Year"', rows[0]["average_annual_returns"])

    def test_projects_llm_wrapper_back_to_source_value(self) -> None:
        markdown = "Average Annual Total Returns (for the periods ended December 31, 2024)"
        response = {
            "fields": {
                "average_annual_returns": {
                    "as_of_date": "as of December 31, 2024",
                    "periods": [],
                }
            }
        }
        result = normalize_response(response, markdown, nested_schema(), "fund.pdf")
        self.assertEqual(
            result["fields"]["average_annual_returns"]["as_of_date"],
            "December 31, 2024",
        )

    def test_projection_preserves_source_numeric_formatting(self) -> None:
        source = "Amount: $19.7000"
        self.assertEqual(project_source_value(source, "the amount is $19.7000"), "$19.7000")
        self.assertIsNone(project_source_value(source, "the amount is $19.70"))

    def test_projection_uses_numeric_polarity_to_disambiguate(self) -> None:
        source = "Positive 2.17 Negative (2.17)"
        self.assertEqual(project_source_value(source, "-2.17"), "(2.17)")
        self.assertEqual(project_source_value(source, "2.17"), "2.17")

    def test_projection_rejects_changed_date(self) -> None:
        source = "Average Annual Total Returns (for the periods ended December 31, 2024)"
        self.assertIsNone(project_source_value(source, "as of December 31, 2025"))

    def test_projection_returns_complete_source_span_when_model_omits_words(self) -> None:
        source = "Baso (Absolute) 02 | 0.1 | x10E3/uL"
        self.assertEqual(
            project_source_value(source, "Baso 02"),
            "Baso (Absolute) 02",
        )

    def test_cli_retries_transient_invalid_llm_response(self) -> None:
        markdown = "Average Annual Total Returns\nDecember 31, 2024"
        invalid = {
            "fields": {
                "average_annual_returns": {
                    "as_of_date": "One nested object for every period column",
                    "periods": [],
                }
            }
        }
        valid = {
            "fields": {
                "average_annual_returns": {
                    "as_of_date": "December 31, 2024",
                    "periods": [],
                }
            }
        }
        with patch("backend.run_pdf_to_outputs.call_openrouter", side_effect=[invalid, valid]) as call:
            result = extract_result(Path("fund.pdf"), markdown, nested_schema(), "key", "model")
        self.assertEqual(call.call_count, 2)
        self.assertEqual(
            result["fields"]["average_annual_returns"]["as_of_date"],
            "December 31, 2024",
        )

    def test_prompt_contains_overall_and_field_context(self) -> None:
        system_prompt = prompt_messages(document_schema(), "Invoice INV-123")[0]["content"]
        self.assertIn("Extract invoice details.", system_prompt)
        self.assertIn("invoice_number", system_prompt)
        self.assertIn("The printed invoice date.", system_prompt)

    def test_candidate_evidence_is_compact_and_keeps_mapping_context(self) -> None:
        evidence = compact_candidate_evidence(
            {
                "fields": [
                    {
                        "label": "Manufacturer",
                        "value": "Acme Ltd.",
                        "confidence": 0.98,
                        "source": {
                            "page": 2,
                            "bbox": {"left": 10, "top": 20, "right": 30, "bottom": 40},
                        },
                    },
                    {"label": "Empty label", "value": "", "source": {"page": 3}},
                ],
                "tables": [
                    {
                        "id": "table-1",
                        "pages": [4],
                        "columns": ["Property", "Result"],
                        "rows": [{"Property": "Density", "Result": "0.9500"}],
                        "cells": [{"large": "parser metadata"}],
                        "confidence": 0.97,
                    }
                ],
                "review": [
                    {
                        "label": "Issue date",
                        "markdown": "16/09/2026",
                        "coordinates": ["18/09/2026"],
                        "reason": "Evidence disagrees",
                    }
                ],
                "unlabeled": [{"text": "A long paragraph that must not enter the model prompt."}],
            }
        )
        self.assertEqual("Manufacturer", evidence["document_fields"][0][1])
        self.assertEqual([2], evidence["document_fields"][0][3])
        self.assertEqual(1, len(evidence["document_fields"]))
        self.assertEqual("0.9500", evidence["tables"][0]["rows"][0][1])
        self.assertNotIn("cells", evidence["tables"][0])
        self.assertEqual(
            ["16/09/2026", "18/09/2026"],
            evidence["ambiguous_fields"][0][2],
        )

    def test_candidate_prompt_maps_descriptions_without_full_markdown(self) -> None:
        evidence = {
            "document_field_columns": ["id", "label", "value", "pages", "source_line"],
            "document_fields": [["field-1", "Manufacturer", "Acme Ltd.", [1], 4]],
            "tables": [],
            "ambiguous_field_columns": [],
            "ambiguous_fields": [],
            "text_candidate_columns": [],
            "text_candidates": [],
        }
        system_prompt = candidate_prompt_messages(document_schema(), evidence)[0]["content"]
        self.assertIn("The printed invoice identifier.", system_prompt)
        self.assertIn('"field-1","Manufacturer","Acme Ltd."', system_prompt)
        self.assertIn("Prefer an empty value over a weak", system_prompt)
        self.assertNotIn("SOURCE MARKDOWN", system_prompt)

    def test_normalize_document_and_preserve_printed_values(self) -> None:
        markdown = "Invoice: INV-123\nDate: 14/09/2026\nTags: red, blue\nAmount: 19.7000"
        response = {
            "fields": {
                "invoice_number": "INV-123",
                "invoice_date": "14/09/2026",
                "tags": ["red", "blue"],
            }
        }
        result = normalize_response(response, markdown, document_schema(), "invoice.pdf")
        self.assertEqual(result["fields"]["invoice_date"], "14/09/2026")
        self.assertEqual(result["fields"]["tags"], ["red", "blue"])
        columns, rows = csv_rows(result, document_schema())
        self.assertEqual(columns, ["source_file", "invoice_number", "invoice_date", "tags"])
        self.assertEqual(rows[0]["tags"], '["red","blue"]')

    def test_normalize_records(self) -> None:
        markdown = "Invoice INV-123\nMaterial A 10.000\nMaterial B 2"
        response = {
            "fields": {"invoice_number": "INV-123"},
            "records": [
                {"description": "Material A", "quantity": "10.000"},
                {"description": "Material B", "quantity": "2"},
            ],
        }
        result = normalize_response(response, markdown, record_schema(), "invoice.pdf")
        columns, rows = csv_rows(result, record_schema())
        self.assertEqual(columns, ["source_file", "invoice_number", "description", "quantity"])
        self.assertEqual(rows[0]["quantity"], "10.000")
        self.assertEqual(rows[1]["description"], "Material B")

    def test_normalized_records_include_table_metadata_and_columns(self) -> None:
        schema = ExtractionSchema.from_mapping(
            {
                "schema_version": 1,
                "name": "invoice",
                "description": "Extract invoice rows.",
                "fields": [],
                "table": {
                    "name": "line_items",
                    "description": "Each line.",
                    "fields": [{"name": "description", "description": "The line description."}],
                },
            }
        )
        result = normalize_response(
            {"fields": {}, "records": []},
            "No line items",
            schema,
            "invoice.pdf",
        )
        self.assertEqual(
            {"name": "line_items", "description": "Each line.", "columns": ["description"], "rows": []},
            result["table"],
        )

    def test_hallucinated_and_truncated_values_are_rejected(self) -> None:
        schema = ExtractionSchema(
            1,
            "amount",
            "Extract the amount.",
            "document",
            (FieldSpec("amount", "number", "Printed amount."),),
        )
        with self.assertRaisesRegex(ValueError, "exact source span"):
            normalize_response({"fields": {"amount": "19.70"}}, "Amount: 19.7000", schema, "a.pdf")
        self.assertFalse(has_exact_source_span("Amount: 19.7000", "19.70"))
        self.assertTrue(has_exact_source_span("Material B 2", "2"))


class CliTests(unittest.TestCase):
    def test_output_files_use_input_stem_output_suffix(self) -> None:
        result = {
            "source_file": "invoice.pdf",
            "fields": {
                "invoice_number": "INV-123",
                "invoice_date": "14/09/2026",
                "tags": [],
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            json_path, csv_path = write_outputs(result, document_schema(), Path(directory), flat_output=True)
            self.assertEqual(json_path.name, "invoice_output.json")
            self.assertEqual(csv_path.name, "invoice_output.csv")
            self.assertTrue(json_path.is_file())
            self.assertTrue(csv_path.is_file())

    def test_single_pdf_is_discovered_recursively(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested = root / "nested"
            nested.mkdir()
            pdf = nested / "input.pdf"
            pdf.write_bytes(b"%PDF")
            self.assertEqual(select_pdf(None, root), pdf.resolve())

    def test_multiple_pdfs_require_explicit_selection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.pdf").write_bytes(b"%PDF")
            (root / "b.pdf").write_bytes(b"%PDF")
            with self.assertRaisesRegex(ValueError, "multiple PDFs"):
                select_pdf(None, root)


if __name__ == "__main__":
    unittest.main()
