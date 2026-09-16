"use client";

import { ChevronDownIcon, InfoCircledIcon } from "@/components/icons";
import { useState } from "react";
import type { AutomaticExtractionResult, AutomaticReviewItem, ExtractionResponse, LegacyExtractionResult } from "@/lib/types";

function isAutomatic(result: ExtractionResponse["result"]): result is AutomaticExtractionResult {
  return "mode" in result && result.mode === "automatic";
}

function display(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Not found";
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

function ReviewList({ items, title, emptyText = "Nothing needs review." }: { items: AutomaticReviewItem[]; title: string; emptyText?: string }) {
  return (
    <section className="review-section">
      <div className="section-heading"><h2>{title}</h2><span>{items.length}</span></div>
      {items.length ? <div className="review-list">{items.map((item, index) => <article key={`${item.page || 0}-${index}`}><strong>{item.label || item.text || "Source content"}</strong>{item.value ? <span>{item.value}</span> : null}{item.markdown ? <span>{item.markdown}</span> : null}<small>{item.reason}{item.page ? ` · page ${item.page}` : ""}</small></article>)}</div> : <p className="empty-state">{emptyText}</p>}
    </section>
  );
}

function MethodDetails({ processing, showMapping }: { processing: ExtractionResponse["processing"]; showMapping: boolean }) {
  const [open, setOpen] = useState(false);
  const contentId = "result-method-details";
  const processingLabel = processing.ocr_used ? "OCR processing" : processing.mode === "automatic" ? "Automatic processing" : "Native text processing";

  return (
    <div className={`method-details ${open ? "open" : ""}`}>
      <button
        type="button"
        className="method-details-button"
        aria-expanded={open}
        aria-controls={contentId}
        onClick={() => setOpen((current) => !current)}
      >
        <InfoCircledIcon aria-hidden="true" />
        <span>Method details</span>
        <ChevronDownIcon aria-hidden="true" />
      </button>
      {open ? <div className="method-details-panel" id={contentId} role="status">
        <div className="method-details-item"><strong>{processingLabel}</strong><span>{processing.note}</span></div>
        {showMapping ? <div className="method-details-item mapping"><strong>Deterministic mapping</strong><span>Markdown structure and PDF coordinates were reconciled. No LLM was used.</span></div> : null}
      </div> : null}
    </div>
  );
}

function AutomaticResults({ result, processing }: { result: AutomaticExtractionResult; processing: ExtractionResponse["processing"] }) {
  const [tab, setTab] = useState<"overview" | "tables" | "review" | "json">("overview");
  const reviewCount = result.review.length;
  return (
    <>
      <header className="pane-header results-header workspace-pane-header">
        <div className="view-tabs" role="tablist" aria-label="Output views">
          {(["overview", "tables", "review", "json"] as const).map((item) => <button key={item} type="button" role="tab" aria-selected={tab === item} onClick={() => setTab(item)}>{item === "overview" ? "Overview" : item[0].toUpperCase() + item.slice(1)}{item === "review" && reviewCount ? ` (${reviewCount})` : ""}</button>)}
        </div>
        <div className="results-header-meta"><p>{result.fields.length} fields · {result.tables.length} tables</p><MethodDetails processing={processing} showMapping /></div>
      </header>
      <div className="results-scroll">
        {tab === "json" ? <pre className="json-output">{JSON.stringify(result, null, 2)}</pre> : null}
        {tab === "overview" ? <div className="table-output automatic-output"><section><div className="section-heading"><h2>Mapped fields</h2><span>{result.fields.length}</span></div><dl className="result-fields automatic-fields">{result.fields.map((field, index) => <div key={`${field.label}-${index}`}><dt>{field.label}</dt><dd className={field.status === "empty" ? "missing" : ""}>{field.status === "empty" ? "Explicitly blank" : field.value}</dd></div>)}</dl></section><ReviewList items={result.unlabeled} title="Unlabeled content" emptyText="No unlabeled content found." /></div> : null}
        {tab === "tables" ? <div className="table-output automatic-output">{result.tables.length ? result.tables.map((table) => <section className="automatic-table" key={table.id}><div className="section-heading"><div><h2>{table.name}</h2><p>Page{table.pages.length === 1 ? "" : "s"} {table.pages.join(", ") || "unknown"}{table.duplicate_pages?.length ? " · repeated copy collapsed" : ""}</p></div><span>{table.rows.length} rows</span></div><div className="records-scroll"><table><thead><tr>{table.columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{table.rows.map((row, rowIndex) => <tr key={rowIndex}>{table.columns.map((column) => <td className={!row[column] ? "empty-cell" : ""} key={column}>{row[column] || ""}</td>)}</tr>)}</tbody></table></div></section>) : <p className="empty-state">No tables were reconstructed.</p>}</div> : null}
        {tab === "review" ? <div className="table-output automatic-output"><ReviewList items={result.review} title="Needs review" /></div> : null}
      </div>
    </>
  );
}

function LegacyResults({ result, processing }: { result: LegacyExtractionResult; processing: ExtractionResponse["processing"] }) {
  const [tab, setTab] = useState<"table" | "json">("table");
  const records = result.table?.rows || result.records || [];
  const columns = result.table?.columns || (records[0] ? Object.keys(records[0]) : []);
  const tableName = result.table?.name || result.schema.replaceAll("_", " ");
  return <><header className="pane-header results-header workspace-pane-header"><div className="view-tabs" role="tablist" aria-label="Output views"><button type="button" role="tab" aria-selected={tab === "table"} onClick={() => setTab("table")}>Table</button><button type="button" role="tab" aria-selected={tab === "json"} onClick={() => setTab("json")}>JSON</button></div><div className="results-header-meta"><p>{records.length ? `${records.length} rows` : result.table ? "0 rows" : "1 document"}</p><MethodDetails processing={processing} showMapping={false} /></div></header><div className="results-scroll">{tab === "json" ? <pre className="json-output">{JSON.stringify(result, null, 2)}</pre> : <div className="table-output"><section><div className="section-heading"><h2>Document fields</h2><span>{Object.keys(result.fields).length}</span></div><dl className="result-fields">{Object.entries(result.fields).map(([key, value]) => <div key={key}><dt>{key}</dt><dd className={display(value) === "Not found" ? "missing" : ""}>{display(value)}</dd></div>)}</dl></section>{result.table || records.length ? <section className="records-output"><div className="section-heading"><div><h2>{tableName}</h2>{result.table?.description ? <p>{result.table.description}</p> : null}</div><span>{records.length} rows</span></div><div className="records-scroll"><table><thead><tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{records.map((record, index) => <tr key={index}>{columns.map((column) => <td key={column}>{display(record[column])}</td>)}</tr>)}</tbody></table>{!records.length ? <p className="empty-state">No matching rows were found.</p> : null}</div></section> : null}</div>}</div></>;
}

export function Results({ response, visible }: { response: ExtractionResponse; visible: boolean }) {
  return <section className={`workspace-pane data-pane results-pane ${visible ? "mobile-visible" : ""}`} aria-labelledby="results-heading"><h2 id="results-heading" className="sr-only">Extraction results</h2>{isAutomatic(response.result) ? <AutomaticResults result={response.result} processing={response.processing} /> : <LegacyResults result={response.result} processing={response.processing} />}</section>;
}
