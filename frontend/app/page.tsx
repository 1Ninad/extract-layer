"use client";

import { ReloadIcon } from "@radix-ui/react-icons";
import { FileText } from "lucide-react";
import { useEffect, useState } from "react";
import { DocumentPanel } from "@/components/document-panel";
import { ExportMenu } from "@/components/export-menu";
import { Results } from "@/components/results";
import { demoResponse } from "@/lib/demo";
import type { ExtractionResponse } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type ExamplePayload = { filename: string; pdf_url: string };

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
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
      setFile(new File([pdf], config.filename, { type: "application/pdf" }));
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
    if (!file) {
      setError("Add a PDF before extracting.");
      return;
    }
    setLoading(true);
    setError("");
    setResponse(null);
    try {
      const form = new FormData();
      form.append("pdf", file);
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
          <div className="product-label" aria-label="Automatic PDF extraction workspace">
            <span className="product-mark" aria-hidden="true"><FileText /></span>
            <span className="product-copy"><span className="product-title">Automatic PDF extraction</span><span className="product-subtitle">PDF to structured data</span></span>
          </div>
          <div className="mobile-tabs" role="tablist" aria-label="Workspace views"><button type="button" role="tab" aria-selected={mobileView === "document"} onClick={() => setMobileView("document")}>Document</button><button type="button" role="tab" aria-selected={mobileView === "data"} onClick={() => setMobileView("data")}>{response ? "Extracted" : "How it works"}</button></div>
          <div className="topbar-actions">{response && !demo ? <button className="secondary-button" type="button" onClick={() => { setResponse(null); setMobileView("data"); }}><ReloadIcon /> Re-run</button> : null}{response ? <ExportMenu response={response} /> : <button className="primary-button" type="button" disabled={loading || exampleLoading || demo || !file} onClick={extract}>{loading ? "Extracting..." : "Extract automatically"}</button>}</div>
        </header>
        <div className="main-workspace">
          <DocumentPanel file={file} onFile={(next) => { setFile(next); setResponse(null); setDemo(false); setError(""); setMobileView("data"); }} onExample={loadExample} exampleLoading={exampleLoading} demo={demo} visible={mobileView === "document"} />
          {response ? <Results response={response} visible={mobileView === "data"} /> : <section className={`workspace-pane data-pane automatic-intro ${mobileView === "data" ? "mobile-visible" : ""}`} aria-labelledby="intro-heading"><header className="pane-header"><div><span className="pane-kicker">Automatic mode</span><h2 id="intro-heading">Ready to map your PDF</h2><p>Upload a document and extraction will discover fields, tables, and anything that needs review.</p></div></header><div className="intro-content"><div><span className="intro-number">01</span><strong>Structure first</strong><p>Markdown text supplies reading order and field boundaries.</p></div><div><span className="intro-number">02</span><strong>Coordinates confirm</strong><p>PDF positions recover sparse rows and visual relationships.</p></div><div><span className="intro-number">03</span><strong>Ambiguity stays visible</strong><p>Uncertain content is preserved for review instead of guessed.</p></div></div></section>}
        </div>
        {error ? <div className="error-bar" role="alert">{error}</div> : null}
      </div>
    </main>
  );
}
