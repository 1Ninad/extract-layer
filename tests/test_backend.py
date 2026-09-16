"""HTTP adapter validation tests that do not invoke external parsers or models."""

from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from pypdf import PdfWriter

from backend.main import app
from backend.main import _run_extraction, _validate_native_markdown
from backend.extraction_schema import ExtractionSchema


class BackendTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_reports_limits(self) -> None:
        response = self.client.get("/api/health")
        self.assertEqual(200, response.status_code)
        self.assertEqual("ok", response.json()["status"])
        self.assertEqual(20, response.json()["max_pdf_pages"])

    def test_schema_validation_rejects_empty_description(self) -> None:
        response = self.client.post(
            "/api/schema/validate",
            json={
                "schema_version": 1,
                "name": "invoice",
                "description": "",
                "output_mode": "document",
                "fields": [{"name": "invoice_number", "type": "text", "description": "Printed invoice number"}],
            },
        )
        self.assertEqual(422, response.status_code)
        self.assertIn("description", response.json()["detail"])

    def test_schema_validation_accepts_human_readable_field_names(self) -> None:
        response = self.client.post(
            "/api/schema/validate",
            json={
                "schema_version": 1,
                "name": "invoice",
                "description": "Extract invoice details.",
                "output_mode": "document",
                "fields": [{"name": "Date of Birth", "type": "text", "description": "Printed date of birth."}],
            },
        )
        self.assertEqual(200, response.status_code)

    def test_schema_validation_still_rejects_invalid_field_names(self) -> None:
        response = self.client.post(
            "/api/schema/validate",
            json={
                "schema_version": 1,
                "name": "invoice",
                "description": "Extract invoice details.",
                "output_mode": "document",
                "fields": [{"name": "Date-of-Birth", "type": "text", "description": "Printed date."}],
            },
        )
        self.assertEqual(422, response.status_code)
        self.assertIn("field name", response.json()["detail"])

    def test_web_records_schema_name_is_accepted(self) -> None:
        response = self.client.post(
            "/api/schema/validate",
            json={
                "schema_version": 1,
                "name": "certificate_of_quality",
                "description": "Extract certificate rows.",
                "output_mode": "records",
                "fields": [{"name": "company_name", "type": "text", "description": "Issuing company."}],
                "records": {
                    "name": "test_results",
                    "description": "One record per result row.",
                    "fields": [{"name": "result", "type": "text", "description": "Printed result."}],
                },
            },
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual({"valid": True}, response.json())

    def test_simple_json_schema_with_table_is_accepted_without_output_mode_or_types(self) -> None:
        response = self.client.post(
            "/api/schema/validate",
            json={
                "schema_version": 1,
                "name": "invoice",
                "description": "Extract invoice details and line items.",
                "fields": [{"name": "invoice_number", "description": "The invoice number."}],
                "table": {
                    "name": "line_items",
                    "description": "Each line item.",
                    "fields": [{"name": "description", "description": "The line description."}],
                },
            },
        )
        self.assertEqual({"valid": True}, response.json())

    def test_simple_json_schema_rejects_both_table_and_legacy_records(self) -> None:
        response = self.client.post(
            "/api/schema/validate",
            json={
                "schema_version": 1,
                "name": "invoice",
                "description": "Extract invoice details.",
                "fields": [{"name": "invoice_number", "description": "The invoice number."}],
                "table": {"name": "items", "description": "Rows.", "fields": [{"name": "value", "description": "Value."}]},
                "records": {"name": "items", "description": "Rows.", "fields": [{"name": "value", "description": "Value."}]},
            },
        )
        self.assertEqual(422, response.status_code)
        self.assertIn("both table and records", response.json()["detail"])

    def test_extraction_accepts_simple_json_schema_form_payload(self) -> None:
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        value = io.BytesIO()
        writer.write(value)
        schema = {
            "schema_version": 1,
            "name": "invoice",
            "description": "Extract invoice rows.",
            "fields": [{"name": "invoice_number", "description": "The invoice number."}],
            "table": {
                "name": "line_items",
                "description": "Each line.",
                "fields": [{"name": "description", "description": "The line description."}],
            },
        }
        processing = {"mode": "native", "ocr_used": False, "note": "Native text processing."}
        with patch(
            "backend.main._run_extraction",
            return_value=(
                {"source_file": "test.pdf", "schema": "invoice", "fields": {}, "records": [], "table": {"name": "line_items", "description": "Each line.", "columns": ["description"], "rows": []}},
                "source_file,invoice_number,description\ntest.pdf,,\n",
                processing,
            ),
        ) as run_extraction:
            response = self.client.post(
                "/api/extractions",
                files={"pdf": ("test.pdf", value.getvalue(), "application/pdf")},
                data={"schema": json.dumps(schema)},
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual("records", run_extraction.call_args.args[2].output_mode)
        self.assertEqual("line_items", run_extraction.call_args.args[2].records.name)

    def test_extraction_rejects_more_than_twenty_pages_before_processing(self) -> None:
        writer = PdfWriter()
        for _ in range(21):
            writer.add_blank_page(width=100, height=100)
        value = io.BytesIO()
        writer.write(value)
        response = self.client.post(
            "/api/extractions",
            files={"pdf": ("too-long.pdf", value.getvalue(), "application/pdf")},
            data={
                "schema": '{"schema_version":1,"name":"test","description":"Test document","output_mode":"document","fields":[{"name":"value","type":"text","description":"Printed test value"}]}'
            },
        )
        self.assertEqual(422, response.status_code)
        self.assertIn("maximum is 20", response.json()["detail"])

    def test_native_failure_retries_complete_pipeline_with_ocr(self) -> None:
        schema = ExtractionSchema.from_mapping(
            {
                "schema_version": 1,
                "name": "test",
                "description": "Test document.",
                "output_mode": "document",
                "fields": [{"name": "value", "type": "text", "description": "Printed value."}],
            }
        )
        result = {"source_file": "test.pdf", "schema": "test", "fields": {"value": "ok"}}
        with patch(
            "backend.main._run_extraction_once",
            side_effect=[ValueError("exact source span failed"), (result, "source_file,value\ntest.pdf,ok\n")],
        ) as run_once:
            extracted, csv_content, processing = _run_extraction(
                b"%PDF-test", "test.pdf", schema, "test-model", use_ocr=False
            )

        self.assertEqual(result, extracted)
        self.assertIn("test.pdf,ok", csv_content)
        self.assertEqual("ocr_fallback", processing["mode"])
        self.assertTrue(processing["ocr_used"])
        self.assertIn("OCR fallback used", processing["note"])
        self.assertEqual(
            [False, True], [call.kwargs["use_ocr"] for call in run_once.call_args_list]
        )

    def test_successful_native_pipeline_reports_that_ocr_was_not_used(self) -> None:
        schema = ExtractionSchema.from_mapping(
            {
                "schema_version": 1,
                "name": "test",
                "description": "Test document.",
                "output_mode": "document",
                "fields": [{"name": "value", "type": "text", "description": "Printed value."}],
            }
        )
        result = {"source_file": "test.pdf", "schema": "test", "fields": {"value": "ok"}}
        with patch("backend.main._run_extraction_once", return_value=(result, "csv")):
            _, _, processing = _run_extraction(
                b"%PDF-test", "test.pdf", schema, "test-model", use_ocr=False
            )

        self.assertEqual("native", processing["mode"])
        self.assertFalse(processing["ocr_used"])
        self.assertIn("OCR not used", processing["note"])

    def test_native_markdown_quality_gate_rejects_empty_and_control_text(self) -> None:
        with self.assertRaisesRegex(ValueError, "no usable text"):
            _validate_native_markdown("\n\t")
        with self.assertRaisesRegex(ValueError, "non-printable"):
            _validate_native_markdown("Portfolio Value: $2ff\x17,222\x1120")
        _validate_native_markdown("Portfolio Value: $274,222.20")

    def test_extraction_response_includes_processing_note(self) -> None:
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        value = io.BytesIO()
        writer.write(value)
        result = {"source_file": "test.pdf", "schema": "test", "fields": {"value": "ok"}}
        processing = {
            "mode": "ocr_fallback",
            "ocr_used": True,
            "note": "OCR fallback used.",
        }
        with patch(
            "backend.main._run_extraction",
            return_value=(result, "source_file,value\ntest.pdf,ok\n", processing),
        ):
            response = self.client.post(
                "/api/extractions",
                files={"pdf": ("test.pdf", value.getvalue(), "application/pdf")},
                data={
                    "schema": '{"schema_version":1,"name":"test","description":"Test document","output_mode":"document","fields":[{"name":"value","type":"text","description":"Printed test value"}]}'
                },
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual(processing, response.json()["processing"])


if __name__ == "__main__":
    unittest.main()
