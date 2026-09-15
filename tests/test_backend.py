"""HTTP adapter validation tests that do not invoke external parsers or models."""

from __future__ import annotations

import io
import unittest

from fastapi.testclient import TestClient
from pypdf import PdfWriter

from backend.main import app


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


if __name__ == "__main__":
    unittest.main()
