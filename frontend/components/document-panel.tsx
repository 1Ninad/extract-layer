"use client";

import { useEffect, useRef, useState } from "react";
import { FileIcon, UploadIcon } from "./icons";

type Props = { file: File | null; previewUrl: string; onFile: (file: File) => void; demo: boolean };

export function DocumentPanel({ file, previewUrl, onFile, demo }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const hasDocument = Boolean(file || demo);
  useEffect(() => setDragging(false), [file]);

  const choose = (candidate?: File) => {
    if (candidate?.type === "application/pdf" || candidate?.name.toLowerCase().endsWith(".pdf")) onFile(candidate);
  };

  return (
    <section className="panel document-panel" aria-labelledby="document-title">
      <div className="panel-heading">
        <div><h2 id="document-title">Document</h2><p>{hasDocument ? (file?.name || "input.pdf") : "Upload one PDF, up to 20 pages"}</p></div>
        {hasDocument ? <button className="secondary-button" type="button" onClick={() => inputRef.current?.click()}>Replace</button> : null}
      </div>
      <input ref={inputRef} type="file" accept="application/pdf,.pdf" hidden onChange={(event) => choose(event.target.files?.[0])} />
      {hasDocument ? (
        <div className="pdf-frame">
          {previewUrl ? <iframe src={`${previewUrl}#toolbar=1&navpanes=0`} title="PDF preview" /> : <DemoDocument />}
        </div>
      ) : (
        <button className={dragging ? "drop-zone dragging" : "drop-zone"} type="button" onClick={() => inputRef.current?.click()} onDragEnter={(event) => { event.preventDefault(); setDragging(true); }} onDragOver={(event) => event.preventDefault()} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); choose(event.dataTransfer.files[0]); }}>
          <span className="upload-icon"><UploadIcon /></span><strong>Choose a PDF or drop it here</strong><span>Digitally generated PDFs work best</span>
        </button>
      )}
      {hasDocument ? <div className="file-meta"><FileIcon /><span>{file?.name || "input.pdf"}</span><small>{file ? `${(file.size / 1024).toFixed(0)} KB` : "1 page"}</small></div> : null}
    </section>
  );
}

function DemoDocument() {
  return <div className="demo-document"><div className="demo-company"><span className="demo-mark">CP</span><div><strong>CONTOSO POLYMERS</strong><small>Technical materials division</small></div></div><h3>CERTIFICATE OF QUALITY</h3><dl><div><dt>Certificate No.</dt><dd>CNT-0041207</dd></div><div><dt>Issue Date</dt><dd>12-Aug-2026</dd></div><div><dt>Order Ref.</dt><dd>PO-58120 / 01-Aug-2026</dd></div><div><dt>Shipment Ref.</dt><dd>SHP-77410 / 10-Aug-2026</dd></div></dl><div className="demo-batch">Batch (Lot): CTXLDE0217A</div><table><thead><tr><th>Property</th><th>Unit</th><th>Result</th><th>Test Method</th></tr></thead><tbody><tr><td>Melt Flow Index</td><td>g/10min</td><td>2.10</td><td>ASTM D1238</td></tr><tr><td>Density</td><td>g/cm3</td><td>0.923</td><td>ASTM D792</td></tr><tr><td>Melting Point</td><td>C</td><td>110</td><td>Internal Method</td></tr><tr><td>Tensile Strength</td><td>MPa</td><td>14.2</td><td>ASTM D638</td></tr></tbody></table><p className="demo-note">Values shown are certified against the stated test methods.</p></div>;
}
