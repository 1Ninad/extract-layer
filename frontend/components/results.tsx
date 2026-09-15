"use client";

import { useState } from "react";
import type { ExtractionResponse } from "@/lib/types";

function display(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Not found";
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

export function Results({ response, visible }: { response: ExtractionResponse; visible: boolean }) {
  const [tab, setTab] = useState<"table" | "json">("table");
  const records = response.result.records || [];
  const columns = records[0] ? Object.keys(records[0]) : [];

  return (
    <section className={`workspace-pane data-pane results-pane ${visible ? "mobile-visible" : ""}`} aria-labelledby="results-heading">
      <header className="pane-header results-header">
        <div className="view-tabs" role="tablist" aria-label="Output views">
          <button type="button" role="tab" aria-selected={tab === "table"} onClick={() => setTab("table")}>Table</button>
          <button type="button" role="tab" aria-selected={tab === "json"} onClick={() => setTab("json")}>JSON</button>
        </div>
        <p>{records.length ? `${records.length} records` : "1 document"}</p>
      </header>
      <div className={`processing-note ${response.processing.ocr_used ? "ocr" : "native"}`} role="status">
        <strong>{response.processing.ocr_used ? "OCR processing" : "Native text processing"}</strong>
        <span>{response.processing.note}</span>
      </div>
      <div className="results-scroll">
        {tab === "json" ? (
          <pre className="json-output">{JSON.stringify(response.result, null, 2)}</pre>
        ) : (
          <div className="table-output">
            <section aria-labelledby="results-heading">
              <div className="section-heading"><h2 id="results-heading">Document fields</h2><span>{Object.keys(response.result.fields).length}</span></div>
              <dl className="result-fields">
                {Object.entries(response.result.fields).map(([key, value]) => <div key={key}><dt>{key}</dt><dd className={display(value) === "Not found" ? "missing" : ""}>{display(value)}</dd></div>)}
              </dl>
            </section>
            {records.length ? (
              <section className="records-output">
                <div className="section-heading"><h2>{response.result.schema.replaceAll("_", " ")}</h2><span>{records.length} rows</span></div>
                <div className="records-scroll"><table><thead><tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{records.map((record, index) => <tr key={index}>{columns.map((column) => <td key={column}>{display(record[column])}</td>)}</tr>)}</tbody></table></div>
              </section>
            ) : null}
          </div>
        )}
      </div>
    </section>
  );
}
