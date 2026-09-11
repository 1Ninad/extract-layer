#!/usr/bin/env python3
"""Map cleaned certificate Markdown into the fixed Excel schema.

The LLM is used only to classify source text into schema fields.  It is not
allowed to normalize, calculate, summarize, or invent values.  Every returned
non-empty value is checked against the source Markdown before it can reach the
workbook.
"""

from __future__ import annotations

import argparse
import json
import os
import string
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


EXCEL_COLUMNS = [
    "Lot",
    "FullText",
    "CertificateExternalId",
    "FileName",
    "OrderNumber",
    "CustomerOrderNumber",
    "ShipmentNumber",
    "DeliveryNumber",
    "TruckOrContainerNumber",
    "Supplier",
    "Grade",
    "Property",
    "TestMethod",
    "Unit",
    "Value",
    "Consignee",
    "ProductionSite",
    "SupplierName",
    "CertificateId",
    "BaseMaterialType",
]

LOCAL_FIELDS = {"FullText", "FileName"}
MAX_LENGTHS = {"SupplierName": 100, "CertificateId": 50, "BaseMaterialType": 50}
EXCEL_CELL_MAX_CHARS = 32767
DEFAULT_MODEL = "mistralai/mistral-small-24b-instruct-2501"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _load_dotenv(path: Path) -> None:
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


def _json_schema() -> dict[str, Any]:
    field_descriptions = {
        "Lot": ("Batch Number or Lot number. Do not use order, delivery, shipment, "
        "certificate, customer/account, or material identifiers."),
        "FullText": "Controlled by the caller; leave empty.",
        "CertificateExternalId": "External certificate identifier; if absent, use the exact printed Delivery Doc Number/Item identifier only when it is the document's stable external id.",
        "FileName": "Controlled by the caller; leave empty.",
        "OrderNumber": (
        "The supplier/seller-side sales order number associated with this transaction, "
        "not its item number or date. Values under an 'Order item/date' style field may "
        "contain '<order number> <item number> / <date>'; extract only the order-number "
        "part when the structure is unambiguous. Do not use Customer Number, Customer PO, "
        "Delivery Number, Shipment Number, Invoice Number, Certificate Number, or Lot Number."
    ),
        "CustomerOrderNumber": (
    "The customer's/buyer's purchase order number, customer order number, or customer-side "
    "order/reference for this transaction. It may appear under labels such as Customer Order, "
    "Customer PO, Purchase Order, PO Number, Buyer Order, Customer Reference, Your Order, "
    "Your PO, or Your Reference when that reference represents the customer's transaction/order. "
    "This identifies WHICH ORDER/reference the customer provided, not WHO the customer is. "
    "Do not use values printed only under Customer, Customer Number, Customer No., Sold To, "
    "Sold-to Party, Account, or similar customer/account identifiers. "
    "Do not use the supplier's own sales order, delivery, shipment, invoice, certificate, or lot number. "
    "If the meaning of a generic reference field is not sufficiently supported by document context, leave empty."
),
        "ShipmentNumber": "Printed Shipment Number only; do not use Shipment Date.",
        "DeliveryNumber": "Printed Delivery Number or Delivery Doc Number/Item identifier.",
        "TruckOrContainerNumber": "Transport/Vehicle Number, truck number, or container number.",
        "Supplier": (
    "The company that supplies/manufactures the material or issues the quality certificate. "
    "Determine this from document-level issuer/manufacturer/seller information such as "
    "company footer, letterhead, certificate issuer, manufacturer block, seller block, "
    "or supplier block. Do not use the customer, buyer, consignee, Ship To, Sold To, "
    "or receiving company. A literal 'Supplier' label is not required. Maximum 100 "
    "characters; never include a long address or footer."
),
        "Grade": (
    "The product grade, resin grade, material grade, or product/material code identifying "
    "the specific commercial material. When a line contains both a compact grade/code and "
    "a descriptive material name, return only the grade/code, not the descriptive material "
    "name. Example pattern: 'ABC123 HIGH DENSITY POLYETHYLENE' -> Grade='ABC123'. "
    "Do not use generic material-family text such as polyethylene, polypropylene, HDPE, LDPE, "
    "unless that is explicitly the only printed grade designation."
),
        "Property": "Characteristic/property name from a result row.",
        "TestMethod": "Method from a result row.",
        "Unit": "Printed unit from a result row.",
        "Value": "Printed result from a result row, including trailing zeroes.",
        "Consignee": (
    "The party receiving the material/shipment represented by the certificate. Prefer an "
    "explicit Consignee, Ship To, Delivery To, Recipient, or receiving-party field. If no "
    "such label exists, an unlabeled customer/address block may be used only when document "
    "structure and business context clearly show that it is the receiving party. "
    "Do not use the supplier, manufacturer, certificate issuer, or seller."
),
        "ProductionSite":  (
    "The explicitly printed place where the material was produced/manufactured, or an "
    "explicit Place of Dispatch when that field represents the source site. Look for labels "
    "such as Production Site, Manufacturing Site, Plant, Mill, Factory, Produced At, "
    "Manufactured At, or Place of Dispatch. Do not infer ProductionSite from the supplier's "
    "company address, headquarters, footer address, customer address, or certificate issuer "
    "address. Leave empty when the production location is not supported."
),
        "SupplierName": (
    "The company that supplies/manufactures the material or issues the quality certificate. "
    "Determine this from document-level issuer/manufacturer/seller information such as "
    "company footer, letterhead, certificate issuer, manufacturer block, seller block, "
    "or supplier block. Do not use the customer, buyer, consignee, Ship To, Sold To, "
    "or receiving company. A literal 'Supplier' label is not required. Maximum 100 "
    "characters; never include a long address or footer."
),
        "CertificateId": "Explicit printed certificate ID/number only; do not invent one.",
        "BaseMaterialType": "Printed material family/type such as PE; maximum 50 characters, no inference.",
    }
    properties = {
        column: {
            "type": "string",
            "description": f"{field_descriptions[column]} Leave empty if absent. When present, copy the exact substring from the Markdown, including case, punctuation, spacing, and zeros.",
        }
        for column in EXCEL_COLUMNS
    }
    return {
        "name": "certificate_excel_rows",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "rows": {
                    "type": "array",
                    "description": (
                        "One object per property/test result. Repeat document-level "
                        "fields on every result row. If there are no result rows, "
                        "return one object containing document-level fields."
                    ),
                    "items": {
                        "type": "object",
                        "properties": properties,
                        "required": EXCEL_COLUMNS,
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["rows"],
            "additionalProperties": False,
        },
    }


def _prompt(markdown: str) -> list[dict[str, str]]:
    system = """You map certificate-of-analysis Markdown into a fixed SQL/Excel row schema.

Rules:
- Use only text that appears in the supplied Markdown.
- Copy every value exactly as written: preserve case, punctuation, HTML entities,
  whitespace inside values, decimal trailing zeros, slashes, and leading zeros.
- Never translate, correct OCR, expand abbreviations, convert units, parse numbers,
  reformat dates, or infer a value that is not printed.
- Return an empty string when a field is absent or not unambiguously supported.
- Do not put Markdown labels into values.
- Create one row per measurement/property result. Put the characteristic name in
  Property, the test method in TestMethod, the printed unit in Unit, and the printed
  result in Value. Repeat certificate-level fields on every measurement row.
- Ignore Min and Max as separate fields because the target schema has no columns for
  them; they remain available in FullText.
- FullText and FileName are controlled by the caller: return them as empty strings.
- Field hints:
  Lot = Batch Number or Lot number only; do not use order, delivery, shipment,
  certificate, customer/account, or material identifiers.
  OrderNumber = supplier/seller-side sales order number; do not use its item
  number, date, customer order, delivery, shipment, invoice, certificate, or lot number.
  CustomerOrderNumber = customer's purchase order, customer order, or customer-side
  transaction/reference; do not use customer/account identifiers or the supplier's
  own sales order.
  ShipmentNumber = printed shipment/shipping/dispatch/consignment number;
  do not use a shipment date.
  DeliveryNumber = printed delivery number or delivery reference.
  TruckOrContainerNumber = truck, vehicle, trailer, or container identifier.
  Supplier and SupplierName = company supplying/manufacturing the material or
  issuing the certificate; do not use the customer, consignee, Ship To, or Sold To.
  SupplierName may be at most 100 characters. Choose a complete exact company-name
  span and never include a long address, footer, or legal disclaimer; if no suitable
  span exists, return an empty string. Never truncate a value.
  Grade = specific product, resin, material, or commercial grade/code; prefer the
  compact grade/code over a descriptive material-family name.
  Consignee = party receiving the material/shipment; prefer Consignee, Ship To,
  Delivery To, Recipient, or receiving-party fields.
  ProductionSite = explicitly printed production/manufacturing location or Place
  of Dispatch when it represents the source site; do not infer it from supplier
  or customer addresses.
  BaseMaterialType = explicitly printed material family/type such as PE.
  CertificateExternalId and CertificateId = explicit printed identifiers only;
  never invent them.
- The response must be only the requested JSON object.
"""
    user = "SOURCE MARKDOWN:\n\n" + markdown
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def call_openrouter(markdown: str, api_key: str, model: str) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": _prompt(markdown),
        "stream": False,
        "provider": {"require_parameters": True},
    }
    payload["response_format"] = {"type": "json_schema", "json_schema": _json_schema()}
    # GPT-5 endpoints do not accept the legacy temperature parameter. Keeping
    # it off only for that family preserves deterministic temperature=0 for
    # compatible models such as GPT-4o-mini.
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
            "X-OpenRouter-Title": "PDF certificate Markdown mapper",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenRouter HTTP {exc.code}: {detail[:1000]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenRouter request failed: {exc.reason}") from exc

    try:
        response_json = json.loads(body)
        message = response_json["choices"][0]["message"]
        content = message.get("content")
        if not content:
            raise ValueError(f"empty model content; message={message!r}")
        parsed = json.loads(content)
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Invalid structured response from OpenRouter: {body[:1500]}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("OpenRouter response JSON must be an object")
    return parsed


def _source_file_name(markdown_path: Path, explicit: str | None) -> str:
    if explicit:
        return explicit
    # Hybrid outputs are stored at output/markdown/<pdf-stem>/hybrid.md.
    if markdown_path.name in {"hybrid.md", "docling_clean.md"} and markdown_path.parent.name:
        return markdown_path.parent.name + ".pdf"
    return markdown_path.name


def _has_exact_source_span(source: str, value: str) -> bool:
    """Reject values that are only a truncated part of a source token.

    A plain substring check would incorrectly accept ``19.7`` from the printed
    ``19.7000``. For numeric-looking values, adjacent digits make the span
    invalid; this preserves trailing and leading zeroes without trying to
    interpret the value.
    """

    start = 0
    while True:
        position = source.find(value, start)
        if position < 0:
            return False
        end = position + len(value)
        previous = source[position - 1] if position else ""
        following = source[end] if end < len(source) else ""
        numeric_value = any(character.isdigit() for character in value)
        adjacent_digit = previous in string.digits or following in string.digits
        if not numeric_value or not adjacent_digit:
            return True
        start = position + 1


def validate_and_normalize(
    response: dict[str, Any],
    markdown: str,
    markdown_path: Path,
    file_name: str | None,
) -> dict[str, Any]:
    if len(markdown) > EXCEL_CELL_MAX_CHARS:
        raise ValueError(
            f"FullText is {len(markdown)} characters; Excel cells support at most "
            f"{EXCEL_CELL_MAX_CHARS}, so refusing to truncate the source"
        )
    raw_rows = response.get("rows")
    if not isinstance(raw_rows, list) or not raw_rows:
        raise ValueError("LLM response must contain a non-empty rows array")

    source_file_name = _source_file_name(markdown_path, file_name)
    rows: list[dict[str, str]] = []
    for index, raw_row in enumerate(raw_rows, start=1):
        if not isinstance(raw_row, dict):
            raise ValueError(f"LLM row {index} is not an object")
        unexpected = set(raw_row) - set(EXCEL_COLUMNS)
        missing = set(EXCEL_COLUMNS) - set(raw_row)
        if unexpected or missing:
            raise ValueError(
                f"LLM row {index} schema mismatch; missing={sorted(missing)}, unexpected={sorted(unexpected)}"
            )

        row: dict[str, str] = {}
        for column in EXCEL_COLUMNS:
            value = raw_row[column]
            if not isinstance(value, str):
                raise ValueError(f"LLM row {index} field {column!r} is not a string")
            if column in LOCAL_FIELDS:
                continue
            if value and not _has_exact_source_span(markdown, value):
                raise ValueError(
                    f"LLM row {index} field {column!r} is not an exact source span in the Markdown: {value!r}"
                )
            max_length = MAX_LENGTHS.get(column)
            if max_length is not None and len(value) > max_length:
                raise ValueError(
                    f"LLM row {index} field {column!r} exceeds its schema limit of {max_length} characters"
                )
            row[column] = value

        # These two fields are deterministic and never trusted to the model.
        row["FullText"] = markdown
        row["FileName"] = source_file_name
        rows.append({column: row[column] for column in EXCEL_COLUMNS})

    return {"columns": EXCEL_COLUMNS, "rows": rows, "source_markdown": str(markdown_path)}


def _find_node(explicit: str | None) -> str:
    if explicit:
        return explicit
    configured = os.environ.get("CODEX_NODE")
    if configured:
        return configured
    return "node"


def write_excel(mapping: dict[str, Any], output_path: Path, node: str | None, node_modules: str | None) -> None:
    writer = Path(__file__).with_name("write_excel.mjs")
    with tempfile.TemporaryDirectory(prefix="pdf-litparse-excel-") as temp_dir:
        temp = Path(temp_dir)
        mapping_path = temp / "mapping.json"
        mapping_path.write_text(json.dumps(mapping, ensure_ascii=False), encoding="utf-8")
        # The spreadsheet skill's bundled runtime is intentionally not copied or modified.
        if node_modules:
            modules_link = temp / "node_modules"
            modules_link.symlink_to(Path(node_modules), target_is_directory=True)
        command = [
            _find_node(node),
            str(writer),
            "--mapping-json",
            str(mapping_path),
            "--output-xlsx",
            str(output_path),
        ]
        environment = os.environ.copy()
        if node_modules:
            environment["PDF_LITPARSE_NODE_MODULES"] = str(Path(node_modules).resolve())
        subprocess.run(command, cwd=temp, check=True, env=environment)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("markdown", type=Path, nargs="+", help="Clean Markdown file(s)")
    parser.add_argument("--output", type=Path, required=True, help="Output .xlsx path")
    parser.add_argument("--file-name", help="Value for FileName; defaults to the PDF stem when available")
    parser.add_argument("--model", default=os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL))
    parser.add_argument("--api-key", default=os.environ.get("OPENROUTER_API_KEY"))
    parser.add_argument("--node", help="Node executable used for the bundled Excel writer")
    parser.add_argument("--node-modules", help="Directory containing @oai/artifact-tool")
    parser.add_argument("--mapping-json", type=Path, help="Optional normalized mapping JSON for audit/debugging")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    _load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    api_key = args.api_key or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY is required (set it in the environment or .env)")
    if not args.node_modules:
        args.node_modules = os.environ.get("CODEX_NODE_MODULES")

    all_rows: list[dict[str, str]] = []
    source_paths: list[str] = []
    for markdown_path in args.markdown:
        markdown = markdown_path.read_text(encoding="utf-8")
        print(f"Mapping {markdown_path} with {args.model}...", flush=True)
        response = call_openrouter(markdown, api_key, args.model)
        mapping = validate_and_normalize(response, markdown, markdown_path, args.file_name)
        all_rows.extend(mapping["rows"])
        source_paths.append(str(markdown_path))

    combined = {"columns": EXCEL_COLUMNS, "rows": all_rows, "source_markdown": source_paths}
    args.output = args.output.resolve()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.mapping_json:
        args.mapping_json.parent.mkdir(parents=True, exist_ok=True)
        args.mapping_json.write_text(json.dumps(combined, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_excel(combined, args.output, args.node, args.node_modules)
    print(f"Wrote {len(all_rows)} row(s) to {args.output}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
