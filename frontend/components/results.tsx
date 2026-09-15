"use client";

import { useState } from "react";
import { CheckIcon, DownloadIcon } from "./icons";
import type { ExtractionResponse } from "@/lib/types";

function readable(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

function download(content: string, name: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const anchor = document.createElement("a");
  anchor.href = url; anchor.download = name; anchor.click();
  URL.revokeObjectURL(url);
}

export function Results({ response }: { response: ExtractionResponse }) {
  const [tab, setTab] = useState<"table" | "json">("table");
  const records = response.result.records || [];
  const columns = records[0] ? Object.keys(records[0]) : [];
  const stem = response.result.source_file.replace(/\.pdf$/i, "_output");
  return (
    <section className="results" aria-labelledby="results-title">
      <div className="result-summary"><span className="success-icon"><CheckIcon /></span><div><h2 id="results-title">Extraction completed</h2><p>{response.page_count} page{response.page_count === 1 ? "" : "s"} processed · {records.length || 1} row{records.length === 1 ? "" : "s"} · {(response.elapsed_ms / 1000).toFixed(1)} seconds</p></div><div className="downloads"><button className="secondary-button" onClick={() => download(response.csv, `${stem}.csv`, "text/csv;charset=utf-8")}><DownloadIcon /> Download CSV</button><button className="secondary-button" onClick={() => download(JSON.stringify(response.result, null, 2), `${stem}.json`, "application/json")}><DownloadIcon /> Download JSON</button></div></div>
      <div className="tabs" role="tablist"><button role="tab" aria-selected={tab === "table"} onClick={() => setTab("table")}>Table</button><button role="tab" aria-selected={tab === "json"} onClick={() => setTab("json")}>JSON</button></div>
      {tab === "json" ? <pre className="json-view">{JSON.stringify(response.result, null, 2)}</pre> : <div className="result-content"><div className="document-fields"><h3>Document fields</h3><dl>{Object.entries(response.result.fields).map(([key, value]) => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{readable(value)}</dd></div>)}</dl></div>{records.length ? <div className="table-region"><h3>{response.result.schema.replaceAll("_", " ")} · {records.length} records</h3><div className="table-scroll"><table><thead><tr>{columns.map((column) => <th key={column}>{column.replaceAll("_", " ")}</th>)}</tr></thead><tbody>{records.map((record, index) => <tr key={index}>{columns.map((column) => <td key={column}>{readable(record[column])}</td>)}</tr>)}</tbody></table></div></div> : null}</div>}
    </section>
  );
}
