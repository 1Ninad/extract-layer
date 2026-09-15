"use client";

import { ReloadIcon } from "@radix-ui/react-icons";
import { useEffect, useMemo, useState } from "react";
import { DocumentPanel } from "@/components/document-panel";
import { ExportMenu } from "@/components/export-menu";
import { Results } from "@/components/results";
import { SchemaBuilder } from "@/components/schema-builder";
import { demoResponse } from "@/lib/demo";
import type { ExtractionResponse, FieldDefinition, SchemaDefinition } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const RECORD_GROUP_NAME = "test_results";
const FIELD_NAME_PATTERN = /^[A-Za-z_][A-Za-z0-9_]*(?: +[A-Za-z_][A-Za-z0-9_]*)*$/;
const RESERVED_FIELD_NAMES = new Set(["source_file", "schema", "fields", "records"]);
const initialFields: FieldDefinition[] = [{ id: "document-field-1", name: "", description: "" }];
const initialRecordFields: FieldDefinition[] = [{ id: "record-field-1", name: "", description: "" }];

type ExamplePayload = {
  filename: string;
  pdf_url: string;
  schema: {
    name: string;
    description: string;
    output_mode: "document" | "records";
    fields: Array<{ name: string; description: string }>;
    records?: { fields: Array<{ name: string; description: string }> };
  };
};

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [schemaName, setSchemaName] = useState("");
  const [description, setDescription] = useState("");
  const [outputMode, setOutputMode] = useState<"document" | "records">("document");
  const [fields, setFields] = useState(initialFields);
  const [recordFields, setRecordFields] = useState(initialRecordFields);
  const [response, setResponse] = useState<ExtractionResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [exampleLoading, setExampleLoading] = useState(false);
  const [demo, setDemo] = useState(false);
  const [mobileView, setMobileView] = useState<"document" | "data">("document");

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("demo") === "1") {
      setDemo(true);
      setResponse(demoResponse);
      return;
    }
  }, []);

  const schema = useMemo<SchemaDefinition>(() => ({
    schema_version: 1,
    name: schemaName.trim(),
    description: description.trim(),
    output_mode: outputMode,
    fields: fields.map(({ id, ...rest }) => ({ ...rest, type: "text" as const, name: rest.name.trim(), description: rest.description.trim() })),
    ...(outputMode === "records" ? { records: { name: RECORD_GROUP_NAME, description: "One record for every matching repeated item or table row.", fields: recordFields.map(({ id, ...rest }) => ({ ...rest, type: "text" as const, name: rest.name.trim(), description: rest.description.trim() })) } } : {}),
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

  async function loadExample() {
    setExampleLoading(true);
    setError("");
    try {
      const configResponse = await fetch("/api/example");
      const configBody = await configResponse.text();
      if (!configResponse.ok) {
        let detail = "Could not load the example schema.";
        try { detail = (JSON.parse(configBody) as { detail?: string }).detail || detail; } catch { /* Keep the readable fallback. */ }
        throw new Error(detail);
      }
      if (!configBody.trim()) throw new Error("The example schema response was empty. Restart the app and try again.");
      let config: ExamplePayload;
      try {
        config = JSON.parse(configBody) as ExamplePayload;
      } catch {
        throw new Error("The example schema response was invalid. Restart the app and try again.");
      }

      const pdfResponse = await fetch(config.pdf_url);
      if (!pdfResponse.ok) throw new Error("Could not load the example PDF.");
      const pdf = await pdfResponse.blob();

      setFile(new File([pdf], config.filename, { type: "application/pdf" }));
      setSchemaName(config.schema.name);
      setDescription(config.schema.description);
      setOutputMode(config.schema.output_mode);
      setFields(config.schema.fields.map((item) => ({ ...item, id: item.name })));
      setRecordFields((config.schema.records?.fields || []).map((item) => ({ ...item, id: item.name })));
      setResponse(null);
      setDemo(false);
      setMobileView("data");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load the example.");
    } finally {
      setExampleLoading(false);
    }
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
      <div className="app-content">
        <header className="topbar">
          <div className="product-label"><span className="product-kicker">PDF extraction</span><span className="product-title">Turn documents into usable data</span></div>
          <div className="mobile-tabs" role="tablist" aria-label="Workspace views">
            <button type="button" role="tab" aria-selected={mobileView === "document"} onClick={() => setMobileView("document")}>Document</button>
            <button type="button" role="tab" aria-selected={mobileView === "data"} onClick={() => setMobileView("data")}>{response ? "Extracted" : "Schema"}</button>
          </div>
          <div className="topbar-actions">
            {response && !demo ? <button className="secondary-button" type="button" onClick={() => { setResponse(null); setMobileView("data"); }}><ReloadIcon /> Re-run</button> : null}
            {response ? <ExportMenu response={response} /> : <button className="primary-button" type="button" disabled={loading || exampleLoading || demo || !valid} onClick={extract}>{loading ? "Extracting..." : "Extract data"}</button>}
          </div>
        </header>

        <div className="main-workspace">
          <DocumentPanel file={file} onFile={(next) => { setFile(next); setResponse(null); setError(""); setMobileView("data"); }} onExample={loadExample} exampleLoading={exampleLoading} demo={demo} visible={mobileView === "document"} />
          {response ? <Results response={response} visible={mobileView === "data"} /> : <SchemaBuilder schemaName={schemaName} description={description} outputMode={outputMode} fields={fields} recordFields={recordFields} disabled={loading} visible={mobileView === "data"} onSchemaName={setSchemaName} onDescription={setDescription} onOutputMode={setOutputMode} onFields={setFields} onRecordFields={setRecordFields} />}
        </div>
        {error ? <div className="error-bar" role="alert">{error}</div> : null}
      </div>
    </main>
  );
}
