"use client";

import { FileTextIcon, ReloadIcon, UploadIcon } from "@radix-ui/react-icons";
import { useRef, useState } from "react";

type Props = {
  file: File | null;
  previewUrl: string;
  onFile: (file: File) => void;
  demo: boolean;
  visible: boolean;
};

export function DocumentPanel({ file, previewUrl, onFile, demo, visible }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const hasDocument = Boolean(file || demo);

  function choose(candidate?: File) {
    if (candidate?.type === "application/pdf" || candidate?.name.toLowerCase().endsWith(".pdf")) {
      onFile(candidate);
      setDragging(false);
    }
  }

  return (
    <section className={`workspace-pane document-pane ${visible ? "mobile-visible" : ""}`} aria-label="PDF document">
      <input ref={inputRef} type="file" accept="application/pdf,.pdf" hidden onChange={(event) => choose(event.target.files?.[0])} />
      {hasDocument ? (
        <>
          <div className="document-toolbar">
            <span><FileTextIcon /> {file?.name || "input.pdf"}</span>
            <button type="button" className="quiet-button" onClick={() => inputRef.current?.click()}><ReloadIcon /> Replace</button>
          </div>
          <div className="pdf-canvas">
            {previewUrl ? <iframe src={`${previewUrl}#toolbar=1&navpanes=0`} title="PDF preview" /> : <DemoDocument />}
          </div>
        </>
      ) : (
        <button
          className={`upload-target ${dragging ? "dragging" : ""}`}
          type="button"
          data-upload-target
          onClick={() => inputRef.current?.click()}
          onDragEnter={(event) => { event.preventDefault(); setDragging(true); }}
          onDragOver={(event) => event.preventDefault()}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => { event.preventDefault(); choose(event.dataTransfer.files[0]); }}
        >
          <UploadIcon />
          <strong>Choose a PDF</strong>
          <span>or drop it here</span>
          <small>One file, up to 20 pages and 25 MB</small>
        </button>
      )}
    </section>
  );
}

function DemoDocument() {
  return (
    <article className="demo-page">
      <header className="certificate-header">
        <div><h2>Contoso Polymers</h2><p>400 Industrial Avenue<br />Houston, TX 77001</p></div>
        <dl><div><dt>Certificate No.</dt><dd>CNT-0041207</dd></div><div><dt>Issue Date</dt><dd>12-Aug-2026</dd></div></dl>
      </header>
      <div className="certificate-rule" />
      <h1>Certificate of Quality</h1>
      <dl className="certificate-meta"><div><dt>Order Ref.</dt><dd>PO-58120 / 01-Aug-2026</dd></div><div><dt>Shipment Ref.</dt><dd>SHP-77410 / 10-Aug-2026</dd></div><div><dt>Customer Code</dt><dd>CUST-10456</dd></div></dl>
      <h3>Batch (Lot): CTXLDE0217A</h3>
      <table><thead><tr><th>Property</th><th>Unit</th><th>Result</th><th>Test method</th></tr></thead><tbody><tr><td>Melt Flow Index</td><td>g/10min</td><td>2.10</td><td>ASTM D1238</td></tr><tr><td>Density</td><td>g/cm3</td><td>0.923</td><td>ASTM D792</td></tr><tr><td>Melting Point</td><td>C</td><td>110</td><td>Internal Method</td></tr><tr><td>Tensile Strength</td><td>MPa</td><td>14.2</td><td>ASTM D638</td></tr></tbody></table>
      <p className="certificate-note">The values above were measured using the stated test methods.</p>
    </article>
  );
}
