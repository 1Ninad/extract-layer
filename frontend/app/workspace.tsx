"use client";

import { ReloadIcon } from "@/components/icons";
import { FileText } from "@phosphor-icons/react";
import { useEffect, useState } from "react";
import { DocumentPanel } from "@/components/document-panel";
import { ExportMenu } from "@/components/export-menu";
import { ExtractionModeChooser } from "@/components/extraction-mode";
import { Results } from "@/components/results";
import { SchemaUpload } from "@/components/schema-upload";
import { demoResponse } from "@/lib/demo";
import { readSchemaFile } from "@/lib/schema";
import type { ExtractionMode, ExtractionResponse, SchemaUploadState } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type ExamplePayload = { filename: string; pdf_url: string; schema: unknown };
type SetupStep = "mode" | "schema";

export function Workspace() {
  const [file, setFile] = useState<File | null>(null);
  const [response, setResponse] = useState<ExtractionResponse | null>(null);
  const [error, setError] = useState("");
  const [schemaError, setSchemaError] = useState("");
  const [loading, setLoading] = useState(false);
  const [schemaValidating, setSchemaValidating] = useState(false);
  const [exampleLoading, setExampleLoading] = useState(false);
  const [demo, setDemo] = useState(false);
  const [exampleQuickTry, setExampleQuickTry] = useState(false);
  const [mode, setMode] = useState<ExtractionMode | null>(null);
  const [setupStep, setSetupStep] = useState<SetupStep>("mode");
  const [schemaUpload, setSchemaUpload] = useState<SchemaUploadState | null>(null);
  const [mobileView, setMobileView] = useState<"document" | "data">("document");

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("demo") === "1") {
      setDemo(true);
      setResponse(demoResponse);
      setMobileView("data");
    }
  }, []);

  async function loadExample() {
    setExampleLoading(true);
    setError("");
    try {
      const configResponse = await fetch("/api/example");
      if (!configResponse.ok) throw new Error("Could not load the example PDF.");
      const config = (await configResponse.json()) as ExamplePayload;
      const pdfResponse = await fetch(config.pdf_url);
      if (!pdfResponse.ok) throw new Error("Could not load the example PDF.");
      const pdf = await pdfResponse.blob();
      const exampleSchemaFile = new File([JSON.stringify(config.schema)], "input.json", { type: "application/json" });
      const parsedSchema = await readSchemaFile(exampleSchemaFile);
      setFile(new File([pdf], config.filename, { type: "application/pdf" }));
      setSchemaUpload(parsedSchema);
      setResponse(null);
      setDemo(false);
      setExampleQuickTry(true);
      setMode(null);
      setSetupStep("mode");
      setMobileView("data");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load the example.");
    } finally {
      setExampleLoading(false);
    }
  }

  async function handleSchemaFile(nextFile: File) {
    setSchemaError("");
    setSchemaValidating(true);
    try {
      const parsed = await readSchemaFile(nextFile);
      const validationResponse = await fetch(`${API_URL}/api/schema/validate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: parsed.raw,
      });
      const payload = await validationResponse.json().catch(() => ({}));
      if (!validationResponse.ok) {
        throw new Error(typeof payload.detail === "string" ? payload.detail : "The schema could not be validated.");
      }
      setSchemaUpload(parsed);
      setSetupStep("schema");
    } catch (caught) {
      setSchemaUpload(null);
      setSchemaError(caught instanceof Error ? caught.message : "The schema could not be read.");
    } finally {
      setSchemaValidating(false);
    }
  }

  function selectMode(nextMode: ExtractionMode) {
    setMode(nextMode);
    setError("");
    if (nextMode === "automatic") setSetupStep("mode");
    if (exampleQuickTry) void extract(nextMode);
  }

  function continueSetup() {
    if (!mode) return;
    if (mode === "schema" && !schemaUpload) {
      setSetupStep("schema");
      return;
    }
    void extract();
  }

  async function extract(modeOverride?: ExtractionMode) {
    if (!file) {
      setError("Add a PDF before extracting.");
      return;
    }
    const selectedMode = modeOverride || mode;
    if (!selectedMode) {
      setError("Choose an extraction mode first.");
      return;
    }
    if (selectedMode === "schema" && !schemaUpload) {
      setSetupStep("schema");
      return;
    }
    setLoading(true);
    setError("");
    setResponse(null);
    try {
      const form = new FormData();
      form.append("pdf", file);
      if (selectedMode === "schema" && schemaUpload) form.append("schema", schemaUpload.raw);
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

  function changePdf(next: File) {
    setFile(next);
    setResponse(null);
    setDemo(false);
    setExampleQuickTry(false);
    setError("");
    setSchemaError("");
    setSetupStep("mode");
    setMobileView("data");
  }

  function startOver() {
    setFile(null);
    setResponse(null);
    setMode(null);
    setSchemaUpload(null);
    setSchemaError("");
    setError("");
    setDemo(false);
    setExampleQuickTry(false);
    setSetupStep("mode");
    setMobileView("document");
  }

  function openPdfPicker() {
    document.getElementById("pdf-file-input")?.click();
  }

  const actionLabel = response
    ? "Run again"
    : !file
      ? "Upload PDF"
      : mode === "automatic"
        ? "Extract automatically"
        : mode === "schema" && schemaUpload
          ? "Extract with schema"
          : mode === "schema"
            ? "Choose JSON schema"
            : "Choose extraction";

  return (
    <main className="app-shell" id="workspace">
      <div className="app-content">
        <header className="focus-header workspace-header">
          <div className="landing-container workspace-header-inner">
          <a className="landing-logo workspace-logo" href="/" aria-label="Document to Structured Data home">
            <span className="landing-logo-mark" aria-hidden="true"><FileText weight="fill" /></span>
            <span className="workspace-logo-full">Document to Structured Data</span>
            <span className="workspace-logo-compact">Doc → Data</span>
          </a>
          <div className="mobile-tabs" role="tablist" aria-label="Workspace views"><button type="button" role="tab" aria-selected={mobileView === "document"} onClick={() => setMobileView("document")}>Document</button><button type="button" role="tab" aria-selected={mobileView === "data"} onClick={() => setMobileView("data")}>{response ? "Extracted" : "Configure"}</button></div>
          <div className="workspace-header-actions">
            {file || demo ? <button className="quiet-button start-over-button" type="button" onClick={startOver}>Start over</button> : null}
            {response && !demo ? <button className="secondary-button" type="button" onClick={() => void extract()} disabled={loading}><ReloadIcon /> {loading ? "Extracting..." : "Run again"}</button> : null}
            {response ? <ExportMenu response={response} /> : <button className="primary-button" type="button" disabled={loading || exampleLoading || demo} onClick={file ? continueSetup : openPdfPicker}>{loading ? "Extracting..." : actionLabel}</button>}
          </div>
          </div>
        </header>
        <div className="workspace-frame">
          <h1 className="sr-only">Document to Structured Data workspace</h1>
          <div className="main-workspace">
            <DocumentPanel file={file} onFile={changePdf} onExample={loadExample} exampleLoading={exampleLoading} demo={demo} visible={mobileView === "document"} />
            {!file && !response ? <section className={`workspace-pane data-pane automatic-intro ${mobileView === "data" ? "mobile-visible" : ""}`} aria-labelledby="intro-heading"><header className="pane-header workspace-pane-header"><div><span className="pane-kicker">Set up extraction</span><h2 id="intro-heading">Upload a PDF to begin</h2></div></header><div className="intro-content"><div><strong>Automatic extraction</strong><p>Find fields, tables, and content that needs review.</p></div><div><strong>Schema extraction</strong><p>Return only the values and table rows you define.</p></div></div></section> : null}
            {file && !response && setupStep === "mode" ? <ExtractionModeChooser selected={mode} visible={mobileView === "data"} hasSchema={Boolean(schemaUpload)} onSelect={selectMode} onContinue={continueSetup} /> : null}
            {file && !response && setupStep === "schema" ? <SchemaUpload schema={schemaUpload?.schema || null} fileName={schemaUpload?.fileName || ""} error={schemaError} validating={schemaValidating} visible={mobileView === "data"} onFile={handleSchemaFile} onBack={() => setSetupStep("mode")} /> : null}
            {response ? <Results response={response} visible={mobileView === "data"} /> : null}
          </div>
        </div>
          {error ? <div className="error-bar" role="alert">{error}</div> : null}
      </div>
    </main>
  );
}
