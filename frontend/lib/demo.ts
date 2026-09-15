import type { ExtractionResponse } from "./types";

export const demoResponse: ExtractionResponse = {
  page_count: 1,
  elapsed_ms: 18342,
  processing: { mode: "automatic", ocr_used: false, note: "Example output. No PDF processing was run." },
  csv: "source_file,Certificate No.,Issue Date,Property,Unit,Result\ninput.pdf,CNT-0041207,12-Aug-2026,Density,g/cm3,0.923\n",
  result: {
    source_file: "input.pdf",
    mode: "automatic",
    fields: [
      { label: "Certificate No.", value: "CNT-0041207", confidence: 0.98, evidence: ["markdown", "coordinates"], status: "accepted" },
      { label: "Issue Date", value: "12-Aug-2026", confidence: 0.98, evidence: ["markdown", "coordinates"], status: "accepted" },
    ],
    tables: [{ id: "table-1", name: "Table 1", pages: [1], columns: ["Property", "Unit", "Result"], header_rows: [["Property", "Unit", "Result"]], rows: [{ Property: "Density", Unit: "g/cm3", Result: "0.923" }], grid: [["Property", "Unit", "Result"], ["Density", "g/cm3", "0.923"]], cells: [], bbox: null, confidence: 0.97, status: "accepted" }],
    unlabeled: [{ text: "Contoso Polymers", reason: "Unlabeled source text", page: 1 }],
    review: [{ text: "Customer United States", reason: "No unique label/value relationship", page: 1 }],
    mapping: { markdown: true, coordinates: true, llm: false },
  },
};
