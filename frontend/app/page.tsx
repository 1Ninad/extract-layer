"use client";

import { useEffect, useMemo, useState } from "react";
import { DocumentPanel } from "@/components/document-panel";
import { SchemaBuilder } from "@/components/schema-builder";
import { Results } from "@/components/results";
import { demoResponse } from "@/lib/demo";
import type { ExtractionResponse, FieldDefinition, SchemaDefinition } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const field = (name: string, description: string): FieldDefinition => ({ id: name, name, type: "text", description });
const initialFields = [field("company_name", "Issuing company shown in the header or footer"), field("reference_code", "Exact value printed next to Certificate No."), field("issued_on", "Exact date printed next to Issue Date")];
const initialRecordFields = [field("lot_number", "Batch or lot containing this result"), field("characteristic", "Exact property or characteristic name"), field("unit", "Exact unit for this result"), field("result", "Exact printed result, including symbols"), field("test_method", "Exact test method or standard")];

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [schemaName, setSchemaName] = useState("certificate_of_quality");
  const [description, setDescription] = useState("Extract certificate identifiers and one record for each characteristic result. Preserve values exactly as printed.");
  const [outputMode, setOutputMode] = useState<"document" | "records">("records");
  const [fields, setFields] = useState(initialFields);
  const [recordFields, setRecordFields] = useState(initialRecordFields);
  const [response, setResponse] = useState<ExtractionResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [demo, setDemo] = useState(false);
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("demo") === "1") {
      setDemo(true); setResponse(demoResponse); setApiOnline(true); return;
    }
    const controller = new AbortController();
    fetch(`${API_URL}/api/health`, { signal: controller.signal })
      .then((result) => setApiOnline(result.ok))
      .catch(() => setApiOnline(false));
    return () => controller.abort();
  }, []);
  useEffect(() => { if (!file) { setPreviewUrl(""); return; } const url = URL.createObjectURL(file); setPreviewUrl(url); return () => URL.revokeObjectURL(url); }, [file]);

  const schema = useMemo<SchemaDefinition>(() => ({ schema_version: 1, name: schemaName.trim(), description: description.trim(), output_mode: outputMode, fields: fields.map(({ id, ...rest }) => rest), ...(outputMode === "records" ? { records: { name: "records", description: "One record for every matching repeated item or table row.", fields: recordFields.map(({ id, ...rest }) => rest) } } : {}) }), [schemaName, description, outputMode, fields, recordFields]);
  const valid = Boolean(file && schema.name && schema.description && schema.fields.every((item) => item.name && item.description) && (outputMode === "document" || recordFields.every((item) => item.name && item.description)));

  async function extract() {
    if (!file || !valid) { setError("Add a PDF and complete every schema field before extracting."); return; }
    setLoading(true); setError(""); setResponse(null);
    const form = new FormData(); form.append("pdf", file); form.append("schema", JSON.stringify(schema));
    try {
      const result = await fetch(`${API_URL}/api/extractions`, { method: "POST", body: form });
      const payload = await result.json();
      if (!result.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "Extraction failed.");
      setResponse(payload as ExtractionResponse);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not reach the extraction API."); }
    finally { setLoading(false); }
  }

  return <main>
    <header className="app-header"><div className="brand"><span className="brand-mark">D</span><div><strong>Document to Database</strong><small>Schema-driven PDF extraction</small></div></div><span className={apiOnline === false ? "api-status offline" : "api-status"}><i /> {apiOnline === null ? "Checking API" : apiOnline ? "API ready" : "API unavailable"}</span></header>
    <div className="page-shell">
      <nav className="steps" aria-label="Extraction steps"><span className="complete"><b>1</b> Upload</span><i /><span className={file || demo ? "complete" : ""}><b>2</b> Define schema</span><i /><span className={response ? "complete" : ""}><b>3</b> Review output</span></nav>
      <div className="workspace"><DocumentPanel file={file} previewUrl={previewUrl} onFile={(next) => { setFile(next); setResponse(null); setError(""); }} demo={demo} /><SchemaBuilder schemaName={schemaName} description={description} outputMode={outputMode} fields={fields} recordFields={recordFields} disabled={loading || demo} onSchemaName={setSchemaName} onDescription={setDescription} onOutputMode={setOutputMode} onFields={setFields} onRecordFields={setRecordFields} /></div>
      <div className="action-row"><div>{error ? <p className="error" role="alert">{error}</p> : <p>Values are returned exactly as printed. Missing values are left empty.</p>}</div><button className="primary-button" disabled={loading || demo || !valid} onClick={extract}>{loading ? "Extracting…" : "Extract data"}</button></div>
      {response ? <Results response={response} /> : null}
    </div>
  </main>;
}
