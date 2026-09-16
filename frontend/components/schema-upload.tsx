"use client";

import { ArrowLeftIcon, CheckCircledIcon, DownloadIcon, FileTextIcon, UploadIcon } from "@/components/icons";
import { useRef, useState } from "react";
import { downloadFile } from "@/lib/download";
import { exampleSchema, schemaSummary } from "@/lib/schema";
import type { SchemaDefinition } from "@/lib/types";

type Props = {
  schema: SchemaDefinition | null;
  fileName: string;
  error: string;
  validating: boolean;
  visible: boolean;
  onFile: (file: File) => void;
  onBack: () => void;
};

export function SchemaUpload({ schema, fileName, error, validating, visible, onFile, onBack }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  function choose(file?: File) {
    if (!file) return;
    onFile(file);
    setDragging(false);
  }

  function downloadExample() {
    downloadFile(`${JSON.stringify(exampleSchema, null, 2)}\n`, "example-schema.json", "application/json");
  }

  return (
    <section className={`workspace-pane data-pane schema-upload-pane ${visible ? "mobile-visible" : ""}`} aria-labelledby="schema-upload-heading">
      <header className="pane-header schema-upload-header workspace-pane-header">
        <button className="quiet-button back-button" type="button" onClick={onBack}><ArrowLeftIcon aria-hidden="true" /> Back</button>
        <div><span className="pane-kicker">Schema mode</span><h2 id="schema-upload-heading">Upload your JSON schema</h2></div>
      </header>
      <div className="schema-upload-content">
        <input ref={inputRef} type="file" accept="application/json,.json" hidden onChange={(event) => { choose(event.target.files?.[0]); event.currentTarget.value = ""; }} />
        {!schema ? (
          <>
            <div className={`schema-drop-target ${dragging ? "dragging" : ""}`} onDragEnter={(event) => { event.preventDefault(); setDragging(true); }} onDragOver={(event) => event.preventDefault()} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); choose(event.dataTransfer.files[0]); }}>
              <button type="button" className="upload-choose" onClick={() => inputRef.current?.click()}>
                <UploadIcon aria-hidden="true" />
                <strong>Choose a JSON file</strong>
                <span>or drop it here</span>
              </button>
            </div>
            <div className="schema-example"><p>Keep it simple. Add field names and descriptions. Add a table only when the PDF contains repeated rows.</p><button className="quiet-button" type="button" onClick={downloadExample}><DownloadIcon aria-hidden="true" /> Download example</button></div>
          </>
        ) : (
          <div className="schema-loaded" aria-live="polite">
            <div className="schema-loaded-heading"><span className="schema-file-icon"><FileTextIcon aria-hidden="true" /></span><div><strong>{fileName}</strong><span>JSON schema validated</span></div><CheckCircledIcon className="schema-check" aria-hidden="true" /></div>
            <div className="schema-summary"><div><span>Schema</span><strong>{schema.name}</strong></div><div><span>Includes</span><strong>{schemaSummary(schema)}</strong></div>{schema.table ? <div><span>Table</span><strong>{schema.table.name}</strong></div> : null}</div>
            <button className="secondary-button replace-schema-button" type="button" onClick={() => inputRef.current?.click()} disabled={validating}><UploadIcon aria-hidden="true" /> Replace schema</button>
          </div>
        )}
        {validating ? <p className="schema-status" role="status">Checking schema...</p> : null}
        {error ? <p className="schema-inline-error" role="alert">{error}</p> : null}
      </div>
    </section>
  );
}
