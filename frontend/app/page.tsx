"use client";

import { FileTextIcon, PlusIcon, ReloadIcon } from "@radix-ui/react-icons";
import { useEffect, useMemo, useState } from "react";
import { DocumentPanel } from "@/components/document-panel";
import { ExportMenu } from "@/components/export-menu";
import { Results } from "@/components/results";
import { SchemaBuilder } from "@/components/schema-builder";
import { demoResponse } from "@/lib/demo";
import type { ExtractionResponse, FieldDefinition, SchemaDefinition } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const RECORD_GROUP_NAME = "test_results";
const FIELD_NAME_PATTERN = /^[A-Za-z_][A-Za-z0-9_]*$/;
const RESERVED_FIELD_NAMES = new Set(["source_file", "schema", "fields", "records"]);
const field = (name: string, description: string): FieldDefinition => ({ id: name, name, type: "text", description });
const initialFields = [
  field("company_name", "Issuing company shown in the header or footer"),
  field("reference_code", "Exact value printed next to Certificate No."),
  { ...field("issued_on", "Exact date printed next to Issue Date"), type: "date" as const },
];
const initialRecordFields = [
  field("lot_number", "Batch or lot containing this result"),
  field("characteristic", "Exact property or characteristic name"),
  field("unit", "Exact unit for this result"),
  field("result", "Exact printed result, including symbols"),
  field("test_method", "Exact test method or standard"),
];

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
  const [mobileView, setMobileView] = useState<"document" | "data">("document");

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("demo") === "1") {
      setDemo(true);
      setResponse(demoResponse);
      setApiOnline(true);
      return;
    }
    const controller = new AbortController();
    fetch(`${API_URL}/api/health`, { signal: controller.signal }).then((result) => setApiOnline(result.ok)).catch(() => setApiOnline(false));
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!file) { setPreviewUrl(""); return; }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const schema = useMemo<SchemaDefinition>(() => ({
    schema_version: 1,
    name: schemaName.trim(),
    description: description.trim(),
    output_mode: outputMode,
    fields: fields.map(({ id, ...rest }) => ({ ...rest, name: rest.name.trim(), description: rest.description.trim() })),
    ...(outputMode === "records" ? { records: { name: RECORD_GROUP_NAME, description: "One record for every matching repeated item or table row.", fields: recordFields.map(({ id, ...rest }) => ({ ...rest, name: rest.name.trim(), description: rest.description.trim() })) } } : {}),
  }), [schemaName, description, outputMode, fields, recordFields]);

  const allFields = outputMode === "records" ? [...schema.fields, ...(schema.records?.fields || [])] : schema.fields;
  const fieldNames = allFields.map((item) => item.name);
  const hasDuplicateFields = new Set(fieldNames).size !== fieldNames.length;
  const valid = Boolean(
    file &&
    schema.name &&
    schema.description &&
    !hasDuplicateFields &&
    allFields.length > 0 &&
    allFields.every((item) => FIELD_NAME_PATTERN.test(item.name) && !RESERVED_FIELD_NAMES.has(item.name) && item.description) &&
    (outputMode === "document" || Boolean(schema.records?.fields.length)),
  );
  const filename = file?.name || (demo ? "input.pdf" : "No document selected");
  const status = loading ? "Extracting" : response ? `Done · ${response.page_count} page${response.page_count === 1 ? "" : "s"} · ${(response.elapsed_ms / 1000).toFixed(1)}s` : apiOnline === false ? "API unavailable" : file ? "Ready to extract" : "Waiting for PDF";

  function chooseAnother() {
    const input = document.querySelector<HTMLInputElement>('input[type="file"]');
    input?.click();
  }

  async function extract() {
    if (!file || !valid) { setError("Add a PDF and complete every schema field before extracting."); return; }
    setLoading(true); setError(""); setResponse(null);
    try {
      const validationResponse = await fetch(`${API_URL}/api/schema/validate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(schema),
      });
      const validationPayload = await validationResponse.json();
      if (!validationResponse.ok) throw new Error(typeof validationPayload.detail === "string" ? validationPayload.detail : "Schema validation failed.");

      const form = new FormData();
      form.append("pdf", file);
      form.append("schema", JSON.stringify(schema));
      const result = await fetch(`${API_URL}/api/extractions`, { method: "POST", body: form });
      const payload = await result.json();
      if (!result.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "Extraction failed.");
      setResponse(payload as ExtractionResponse);
      setMobileView("data");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not reach the extraction API.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="app-shell">
      <aside className="rail" aria-label="Document controls">
        <div className="rail-mark">D</div>
        {file || demo ? <button type="button" className="rail-document active" aria-label={filename}><FileTextIcon /></button> : null}
        <button type="button" className="rail-add" aria-label="Choose another PDF" onClick={chooseAnother}><PlusIcon /></button>
      </aside>

      <div className="app-content">
        <header className="topbar">
          <div className="file-status"><span className="filename">{filename}</span><span role="status" aria-live="polite" className={apiOnline === false ? "status-copy error-status" : "status-copy"}>{status}</span></div>
          <div className="mobile-tabs" role="tablist" aria-label="Workspace views">
            <button type="button" role="tab" aria-selected={mobileView === "document"} onClick={() => setMobileView("document")}>Document</button>
            <button type="button" role="tab" aria-selected={mobileView === "data"} onClick={() => setMobileView("data")}>{response ? "Extracted" : "Schema"}</button>
          </div>
          <div className="topbar-actions">
            {response && !demo ? <button className="secondary-button" type="button" onClick={() => { setResponse(null); setMobileView("data"); }}><ReloadIcon /> Re-run</button> : null}
            {response ? <ExportMenu response={response} /> : <button className="primary-button" type="button" disabled={loading || demo || !valid} onClick={extract}>{loading ? "Extracting..." : "Extract data"}</button>}
          </div>
        </header>

        <div className="main-workspace">
          <DocumentPanel file={file} previewUrl={previewUrl} onFile={(next) => { setFile(next); setResponse(null); setError(""); setMobileView("data"); }} demo={demo} visible={mobileView === "document"} />
          {response ? <Results response={response} visible={mobileView === "data"} /> : <SchemaBuilder schemaName={schemaName} description={description} outputMode={outputMode} fields={fields} recordFields={recordFields} disabled={loading} visible={mobileView === "data"} onSchemaName={setSchemaName} onDescription={setDescription} onOutputMode={setOutputMode} onFields={setFields} onRecordFields={setRecordFields} />}
        </div>
        {error ? <div className="error-bar" role="alert">{error}</div> : null}
      </div>
    </main>
  );
}
