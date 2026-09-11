#!/usr/bin/env python3
"""Convert PDFs to Markdown with Docling."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def convert(
    input_pdf: Path,
    output_md: Path,
    use_ocr: bool = False,
    output_html: Path | None = None,
    output_json: Path | None = None,
) -> None:
    from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
    from docling.document_converter import DocumentConverter, PdfFormatOption

    options = PdfPipelineOptions(
        do_ocr=use_ocr,
        do_table_structure=True,
    )
    options.table_structure_options.mode = TableFormerMode.ACCURATE
    # The PDF has native text and a two-line table. Let TableFormer's
    # predicted cells define the grid instead of matching native text cells
    # into the grid, which can merge adjacent characteristics/methods.
    options.table_structure_options.do_cell_matching = False
    converter = DocumentConverter(
        format_options={"pdf": PdfFormatOption(pipeline_options=options)}
    )
    result = converter.convert(str(input_pdf))
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(result.document.export_to_markdown(), encoding="utf-8")
    if output_html is not None:
        output_html.parent.mkdir(parents=True, exist_ok=True)
        output_html.write_text(result.document.export_to_html(), encoding="utf-8")
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(
            json.dumps(result.document.export_to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_pdf", type=Path)
    parser.add_argument("output_md", type=Path)
    parser.add_argument("--output-html", type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--ocr", action="store_true", help="Enable full-page OCR")
    args = parser.parse_args()
    convert(
        args.input_pdf,
        args.output_md,
        use_ocr=args.ocr,
        output_html=args.output_html,
        output_json=args.output_json,
    )


if __name__ == "__main__":
    main()
