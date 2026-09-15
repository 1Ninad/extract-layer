"use client";

import { FileTextIcon, UploadIcon } from "@radix-ui/react-icons";
import { FilePenLine } from "lucide-react";
import { useEffect, useRef, useState } from "react";

type Props = {
  file: File | null;
  onFile: (file: File) => void;
  onExample: () => void;
  exampleLoading: boolean;
  demo: boolean;
  visible: boolean;
};

type PdfDocument = {
  numPages: number;
  getPage: (pageNumber: number) => Promise<PdfPage>;
};

type PdfPage = {
  getViewport: (options: { scale: number }) => PdfViewport;
  render: (options: { canvasContext: CanvasRenderingContext2D; viewport: PdfViewport; transform?: [number, number, number, number, number, number]; background?: string }) => { promise: Promise<void>; cancel: () => void };
};

type PdfViewport = { width: number; height: number; [key: string]: unknown };

export function DocumentPanel({ file, onFile, onExample, exampleLoading, demo, visible }: Props) {
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
          <div className="pdf-canvas">
            {file ? <PdfDocumentViewer file={file} /> : <DemoDocument />}
          </div>
          <div className="document-actions">
            <span>Document preview</span>
            <button type="button" className="quiet-button change-pdf-button" onClick={() => inputRef.current?.click()}>
              <FilePenLine aria-hidden="true" />
              Change PDF
            </button>
          </div>
        </>
      ) : (
        <div
          className={`upload-target ${dragging ? "dragging" : ""}`}
          data-upload-target
          onDragEnter={(event) => { event.preventDefault(); setDragging(true); }}
          onDragOver={(event) => event.preventDefault()}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => { event.preventDefault(); choose(event.dataTransfer.files[0]); }}
        >
          <button type="button" className="upload-choose" onClick={() => inputRef.current?.click()}>
            <UploadIcon />
            <strong>Choose a PDF</strong>
            <span>or drop it here</span>
          </button>
          <button type="button" className="example-button" onClick={onExample} disabled={exampleLoading}>
            {exampleLoading ? "Loading example..." : "Try the example"}
          </button>
          <small>One file, up to 20 pages and 25 MB</small>
        </div>
      )}
    </section>
  );
}

function PdfDocumentViewer({ file }: { file: File }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [document, setDocument] = useState<PdfDocument | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    setDocument(null);

    async function load() {
      try {
        const pdfjs = await import("pdfjs-dist");
        pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();
        const loadingTask = pdfjs.getDocument({ data: await file.arrayBuffer() });
        const loaded = await loadingTask.promise;
        if (!cancelled) setDocument(loaded as unknown as PdfDocument);
      } catch {
        if (!cancelled) setError("This PDF could not be previewed. You can still try extracting it.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => { cancelled = true; };
  }, [file]);

  if (loading) {
    return <div className="pdf-state" role="status"><div className="page-skeleton" /><div className="page-skeleton short" /><span>Preparing preview</span></div>;
  }
  if (error) return <div className="pdf-state pdf-error"><FileTextIcon /><strong>Preview unavailable</strong><span>{error}</span></div>;
  if (!document) return null;

  return (
    <div className="pdf-scroll" ref={scrollRef}>
      {Array.from({ length: document.numPages }, (_, index) => (
        <PdfPageCanvas key={index} document={document} pageNumber={index + 1} root={scrollRef} />
      ))}
    </div>
  );
}

function PdfPageCanvas({ document, pageNumber, root }: { document: PdfDocument; pageNumber: number; root: React.RefObject<HTMLDivElement | null> }) {
  const hostRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [active, setActive] = useState(pageNumber === 1);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const observer = new IntersectionObserver(([entry]) => setActive(entry.isIntersecting), { root: root.current, rootMargin: "520px 0px" });
    observer.observe(host);
    return () => observer.disconnect();
  }, [root]);

  useEffect(() => {
    if (!active || !canvasRef.current || !hostRef.current) return;
    let cancelled = false;
    let renderTask: { promise: Promise<void>; cancel: () => void } | null = null;
    let renderGeneration = 0;
    let renderedWidth = 0;

    async function renderPage() {
      const generation = ++renderGeneration;
      const page = await document.getPage(pageNumber);
      if (cancelled || generation !== renderGeneration || !canvasRef.current || !hostRef.current) return;
      const baseViewport = page.getViewport({ scale: 1 });
      const cssWidth = Math.max(1, hostRef.current.clientWidth);
      const scale = cssWidth / baseViewport.width;
      const outputScale = Math.min(window.devicePixelRatio || 1, 2);
      const viewport = page.getViewport({ scale });
      const canvas = canvasRef.current;
      canvas.width = Math.max(1, Math.floor(viewport.width * outputScale));
      canvas.height = Math.max(1, Math.floor(viewport.height * outputScale));
      canvas.style.width = `${viewport.width}px`;
      canvas.style.height = `${viewport.height}px`;
      renderTask?.cancel();
      renderTask = page.render({
        canvasContext: canvas.getContext("2d", { alpha: false }) as CanvasRenderingContext2D,
        viewport,
        transform: outputScale === 1 ? undefined : [outputScale, 0, 0, outputScale, 0, 0],
        background: "#ffffff",
      });
      await renderTask.promise;
    }

    void renderPage().catch(() => undefined);
    const resizeObserver = new ResizeObserver(([entry]) => {
      const width = Math.round(entry.contentRect.width);
      if (width !== renderedWidth) {
        renderedWidth = width;
        void renderPage().catch(() => undefined);
      }
    });
    resizeObserver.observe(hostRef.current);
    return () => {
      cancelled = true;
      renderTask?.cancel();
      resizeObserver.disconnect();
    };
  }, [active, document, pageNumber]);

  return <div className="pdf-page-shell" ref={hostRef}><canvas ref={canvasRef} aria-label={`Page ${pageNumber}`} /></div>;
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
