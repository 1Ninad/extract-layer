"use client";

import { ArrowRightIcon, FileTextIcon, LightningBoltIcon } from "@/components/icons";
import type { ExtractionMode } from "@/lib/types";

type Props = {
  selected: ExtractionMode | null;
  visible: boolean;
  hasSchema: boolean;
  onSelect: (mode: ExtractionMode) => void;
  onContinue: () => void;
};

export function ExtractionModeChooser({ selected, visible, hasSchema, onSelect, onContinue }: Props) {
  return (
    <section className={`workspace-pane data-pane mode-pane ${visible ? "mobile-visible" : ""}`} aria-labelledby="mode-heading">
      <header className="pane-header workspace-pane-header"><div><span className="pane-kicker">Extraction mode</span><h2 id="mode-heading">Choose how to extract</h2></div></header>
      <div className="mode-content">
        <div className="mode-options" role="radiogroup" aria-label="Extraction mode">
          <button type="button" className={`mode-option ${selected === "automatic" ? "selected" : ""}`} role="radio" aria-checked={selected === "automatic"} onClick={() => onSelect("automatic")}>
            <span className="mode-option-icon"><LightningBoltIcon aria-hidden="true" /></span><span><strong>Automatic extraction</strong><small>Find fields, tables, and content that needs review.</small></span>
          </button>
          <button type="button" className={`mode-option ${selected === "schema" ? "selected" : ""}`} role="radio" aria-checked={selected === "schema"} onClick={() => onSelect("schema")}>
            <span className="mode-option-icon"><FileTextIcon aria-hidden="true" /></span><span><strong>Define a schema</strong><small>Describe the fields you need, or use an existing JSON schema.</small></span>{hasSchema ? <em>Ready</em> : null}
          </button>
        </div>
        <button className="primary-button mode-continue" type="button" disabled={!selected} onClick={onContinue}>{selected === "schema" && !hasSchema ? "Choose schema" : "Continue"}<ArrowRightIcon aria-hidden="true" /></button>
      </div>
    </section>
  );
}
