"use client";

import { ChangeEvent, DragEvent, useEffect, useMemo, useRef, useState } from "react";
import { Icon } from "../components/icons";
import { checkHealth, extractPdf } from "../lib/api";
import type { ExtractionResponse, FieldType, SchemaDefinition, SchemaField } from "../types";

const initialSchema: SchemaDefinition = {
  schema_version: 1,
  name: "certificate_of_quality",
  description: "Extract certificate identifiers and test results. Preserve values exactly as printed in the PDF.",
  output_mode: "records",
  fields: [
    { name: "company_name", type: "text", description: "Issuing company shown in the certificate header or footer." },
    { name: "reference_code", type: "text", description: "Exact value printed next to the certificate number." },
    { name: "issued_on", type: "date", description: "Exact date printed next to the issue date." },
    { name: "order_number", type: "text", description: "Complete value printed next to the order reference." },
  ],
  records: {
    name: "test_results",
    description: "One record for every characteristic row in every batch table.",
    fields: [
      { name: "lot_number", type: "text", description: "Lot number from the nearest preceding batch line." },
      { name: "characteristic", type: "text", description: "Exact text from the property column." },
      { name: "unit", type: "text", description: "Exact value from the unit column." },
      { name: "result", type: "text", description: "Exact value from the result column, including symbols." },
      { name: "test_method", type: "text", description: "Exact value from the test method column." },
    ],
  },
};

const steps = [
  { id: "upload", label: "Upload PDF", icon: "file" as const },
  { id: "schema", label: "Schema", icon: "table" as const },
  { id: "results", label: "Results", icon: "chart" as const },
];

export default function Home() {
  const [schema, setSchema] = useState<SchemaDefinition>(initialSchema);
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ExtractionResponse | null>(null);
  const [activeStep, setActiveStep] = useState("upload");
  const [status, setStatus] = useState("Ready");
  const [error, setError] = useState("");
  const [apiConnected, setApiConnected] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [ocr, setOcr] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    checkHealth().then(() => setApiConnected(true)).catch(() => setApiConnected(false));
  }, []);

  const updateField = (group: "fields" | "records", index: number, patch: Partial<SchemaField>) => {
    setSchema((current) => {
      const fields = group === "fields" ? current.fields : current.records?.fields ?? [];
      const next = fields.map((field, fieldIndex) => fieldIndex === index ? { ...field, ...patch } : field);
      return group === "fields" ? { ...current, fields: next } : { ...current, records: { ...current.records!, fields: next } };
    });
  };

  const addField = (group: "fields" | "records") => {
    const field: SchemaField = { name: group === "records" ? "new_result" : "new_field", type: "text", description: "Describe how to identify this value in the PDF." };
    setSchema((current) => group === "fields"
      ? { ...current, fields: [...current.fields, field] }
      : { ...current, records: { ...current.records!, fields: [...(current.records?.fields ?? []), field] } });
  };

  const removeField = (group: "fields" | "records", index: number) => {
    setSchema((current) => {
      const fields = group === "fields" ? current.fields : current.records?.fields ?? [];
      const next = fields.filter((_, fieldIndex) => fieldIndex !== index);
      return group === "fields" ? { ...current, fields: next } : { ...current, records: { ...current.records!, fields: next } };
    });
  };

  const acceptFile = (candidate: File | undefined) => {
    setError("");
    if (!candidate) return;
    if (candidate.type !== "application/pdf" && !candidate.name.toLowerCase().endsWith(".pdf")) {
      setError("Choose a PDF file.");
      return;
    }
    if (candidate.size > 25 * 1024 * 1024) {
      setError("PDF must be 25 MB or smaller.");
      return;
    }
    setFile(candidate);
    setActiveStep("schema");
    setStatus("PDF ready");
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    acceptFile(event.dataTransfer.files[0]);
  };

  const runExtraction = async () => {
    if (!file) {
      setError("Upload a PDF before running extraction.");
      return;
    }
    setProcessing(true);
    setError("");
    setStatus("Extracting…");
    try {
      const response = await extractPdf(file, schema, ocr);
      setResult(response);
      setActiveStep("results");
      setStatus("Extraction complete");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Extraction failed.");
      setStatus("Action needed");
    } finally {
      setProcessing(false);
    }
  };

  const download = (content: string, filename: string, type: string) => {
    const url = URL.createObjectURL(new Blob([content], { type }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const goTo = (id: string) => {
    setActiveStep(id);
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">D</span><span>DocuTable</span></div>
        <div className="sidebar-caption">WORKSPACE</div>
        <nav className="step-nav" aria-label="Extraction workflow">
          {steps.map((step) => (
            <button key={step.id} className={`step-link ${activeStep === step.id ? "active" : ""}`} onClick={() => goTo(step.id)}>
              <span className="step-icon"><Icon name={step.icon} size={18} /></span><span>{step.label}</span>
              {step.id === "results" && result ? <span className="step-check"><Icon name="check" size={13} /></span> : null}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className={`connection ${apiConnected ? "connected" : ""}`}><span className="status-dot" />{apiConnected ? "API connected" : "API offline"}</div>
          <p>One PDF per extraction<br />Up to 25 MB</p>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div><p className="topbar-kicker">DOCUMENT EXTRACTION</p><h1>New extraction</h1></div>
          <div className="topbar-actions"><div className={`api-status ${apiConnected ? "online" : ""}`}><span className="status-dot" />{apiConnected ? "API connected" : "API offline"}</div><div className="topbar-divider" /><div className="avatar">N</div></div>
        </header>

        <div className="content-area">
          <section id="upload" className="document-panel panel">
            <div className="panel-heading"><div><h2>Document</h2><p>Upload a digitally generated PDF to begin.</p></div><span className="file-limit">1 PDF</span></div>
            {!file ? (
              <div className="dropzone" onDrop={handleDrop} onDragOver={(event) => event.preventDefault()} onClick={() => fileInput.current?.click()} role="button" tabIndex={0} onKeyDown={(event) => { if (event.key === "Enter") fileInput.current?.click(); }}>
                <div className="drop-icon"><Icon name="upload" size={24} /></div><h3>Drop your PDF here</h3><p>or choose a file from your device</p><button className="secondary-button" type="button"><Icon name="file" size={16} /> Choose PDF</button><span className="drop-note">Digital PDFs only · max 25 MB</span>
                <input ref={fileInput} type="file" accept="application/pdf,.pdf" hidden onChange={(event: ChangeEvent<HTMLInputElement>) => acceptFile(event.target.files?.[0])} />
              </div>
            ) : (
              <div className="document-loaded">
                <div className="file-row"><div className="file-badge"><Icon name="file" size={20} /></div><div className="file-details"><strong>{file.name}</strong><span>{formatBytes(file.size)} · PDF document</span></div><button className="text-button" onClick={() => fileInput.current?.click()}>Replace</button><input ref={fileInput} type="file" accept="application/pdf,.pdf" hidden onChange={(event: ChangeEvent<HTMLInputElement>) => acceptFile(event.target.files?.[0])} /></div>
                <div className="pdf-preview"><object data={URL.createObjectURL(file)} type="application/pdf" aria-label="PDF preview"><div className="preview-fallback"><Icon name="file" size={28} /><p>PDF preview is not available in this browser.</p></div></object></div>
                <div className="preview-footer"><span><span className="status-dot green" />File ready for extraction</span><button className="text-button" onClick={() => setFile(null)}>Remove</button></div>
              </div>
            )}
          </section>

          <section id="schema" className="schema-panel panel">
            <div className="panel-heading schema-heading"><div><h2>Schema</h2><p>Tell the extractor which values to return.</p></div><button className="secondary-button small" onClick={() => addField("fields")}><Icon name="plus" size={15} /> Add field</button></div>
            <div className="schema-meta"><label>Schema name<input value={schema.name} onChange={(event) => setSchema({ ...schema, name: event.target.value })} /></label><label>Output shape<select value={schema.output_mode} onChange={(event) => setSchema({ ...schema, output_mode: event.target.value as "document" | "records" })}><option value="records">Document + repeated rows</option><option value="document">Document fields only</option></select></label></div>
            <div className="field-section"><div className="section-title"><div><strong>Document fields</strong><span>Values returned once per PDF</span></div><button className="icon-button" aria-label="Add document field" onClick={() => addField("fields")}><Icon name="plus" size={16} /></button></div><div className="field-list"><div className="field-header"><span>FIELD NAME</span><span>TYPE</span><span>DESCRIPTION</span><span /></div>{schema.fields.map((field, index) => <FieldRow key={`${field.name}-${index}`} field={field} onChange={(patch) => updateField("fields", index, patch)} onRemove={() => removeField("fields", index)} />)}</div></div>
            {schema.output_mode === "records" && schema.records ? <div className="field-section record-section"><div className="section-title"><div><strong>{schema.records.name || "Repeated records"}</strong><span>{schema.records.description}</span></div><button className="icon-button" aria-label="Add record field" onClick={() => addField("records")}><Icon name="plus" size={16} /></button></div><div className="field-list"><div className="field-header"><span>FIELD NAME</span><span>TYPE</span><span>DESCRIPTION</span><span /></div>{schema.records.fields.map((field, index) => <FieldRow key={`${field.name}-${index}`} field={field} onChange={(patch) => updateField("records", index, patch)} onRemove={() => removeField("records", index)} />)}</div></div> : null}
            <div className="schema-options"><label className="checkbox-label"><input type="checkbox" checked={ocr} onChange={(event) => setOcr(event.target.checked)} /><span>Enable OCR fallback</span></label><span className="schema-hint">Source values are preserved exactly.</span></div>
            <div className="run-area"><button className="primary-button" onClick={runExtraction} disabled={processing || !file}>{processing ? <><span className="spinner" /> Running extraction</> : <>Run extraction <Icon name="chevron" size={17} /></>}</button>{!file ? <span className="run-hint">Upload a PDF to enable extraction.</span> : null}</div>
          </section>

          <section id="results" className="results-panel panel">
            <div className="panel-heading"><div><h2>Results</h2><p>{result ? `${result.result.records?.length ?? 0} records extracted from ${result.source_file}` : "Your structured output will appear here after extraction."}</p></div>{result ? <div className="result-actions"><button className="secondary-button small" onClick={() => download(JSON.stringify(result.result, null, 2), result.json_filename, "application/json")}><Icon name="download" size={15} /> JSON</button><button className="secondary-button small" onClick={() => download(result.csv, result.csv_filename, "text/csv")}><Icon name="download" size={15} /> CSV</button></div> : null}</div>
            {result ? <ResultView result={result} /> : <div className="empty-results"><div className="empty-icon"><Icon name="chart" size={24} /></div><strong>Nothing extracted yet</strong><span>Run the schema against your PDF to review the table and download the output.</span></div>}
          </section>
        </div>
        <footer className={`statusbar ${error ? "has-error" : ""}`}><span className="status-dot" />{error || status}<span className="statusbar-right">{file ? file.name : "No document selected"}</span></footer>
      </section>
    </main>
  );
}

function FieldRow({ field, onChange, onRemove }: { field: SchemaField; onChange: (patch: Partial<SchemaField>) => void; onRemove: () => void }) {
  return <div className="field-row"><span className="drag-handle">⋮⋮</span><input aria-label="Field name" value={field.name} onChange={(event) => onChange({ name: event.target.value })} /><select aria-label="Field type" value={field.type} onChange={(event) => onChange({ type: event.target.value as FieldType })}>{["text", "number", "date", "boolean", "array", "object"].map((type) => <option key={type} value={type}>{type}</option>)}</select><input aria-label="Field description" value={field.description} onChange={(event) => onChange({ description: event.target.value })} /><button className="icon-button danger" aria-label={`Remove ${field.name}`} onClick={onRemove}><Icon name="trash" size={16} /></button></div>;
}

function ResultView({ result }: { result: ExtractionResponse }) {
  const [tab, setTab] = useState<"table" | "json" | "csv">("table");
  const records = result.result.records ?? [];
  const columns = records.length ? Object.keys(records[0]) : Object.keys(result.result.fields);
  return <div className="result-view"><div className="result-tabs"><button className={tab === "table" ? "selected" : ""} onClick={() => setTab("table")}>Table</button><button className={tab === "json" ? "selected" : ""} onClick={() => setTab("json")}><Icon name="code" size={14} /> JSON</button><button className={tab === "csv" ? "selected" : ""} onClick={() => setTab("csv")}><Icon name="table" size={14} /> CSV</button><span className="result-count">{records.length} rows</span></div>{tab === "table" ? <div className="table-wrap"><table><thead><tr>{columns.map((column) => <th key={column}>{column.replaceAll("_", " ")}</th>)}</tr></thead><tbody>{(records.length ? records : [result.result.fields]).map((record, index) => <tr key={index}>{columns.map((column) => <td key={column}>{formatValue(record[column])}</td>)}</tr>)}</tbody></table></div> : tab === "json" ? <pre className="code-output">{JSON.stringify(result.result, null, 2)}</pre> : <pre className="code-output csv-output">{result.csv}</pre>}</div>;
}

function formatValue(value: unknown) { return typeof value === "object" && value !== null ? JSON.stringify(value) : String(value ?? "—"); }
function formatBytes(bytes: number) { return bytes < 1024 * 1024 ? `${Math.round(bytes / 1024)} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`; }
