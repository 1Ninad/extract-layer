"use client";

import { ChevronDownIcon, DownloadIcon } from "@/components/icons";
import { useEffect, useRef, useState } from "react";
import { downloadFile } from "@/lib/download";
import type { ExtractionResponse } from "@/lib/types";

export function ExportMenu({ response }: { response: ExtractionResponse }) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const stem = response.result.source_file.replace(/\.pdf$/i, "_output");

  useEffect(() => {
    function close(event: MouseEvent) {
      if (!menuRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  return (
    <div className="export-control" ref={menuRef}>
      <button className="primary-button" type="button" aria-expanded={open} onClick={() => setOpen((value) => !value)}>Export <ChevronDownIcon /></button>
      {open ? (
        <div className="export-menu">
          <button type="button" onClick={() => { downloadFile(response.csv, `${stem}.csv`, "text/csv;charset=utf-8"); setOpen(false); }}><span><DownloadIcon /> Download CSV</span><small>.csv</small></button>
          <button type="button" onClick={() => { downloadFile(JSON.stringify(response.result, null, 2), `${stem}.json`, "application/json"); setOpen(false); }}><span><DownloadIcon /> Download JSON</span><small>.json</small></button>
        </div>
      ) : null}
    </div>
  );
}
