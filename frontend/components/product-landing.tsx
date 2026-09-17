"use client";

import type { ReactNode } from "react";
import { useEffect } from "react";
import { ArrowUpRight, FileText, FlowArrow } from "@phosphor-icons/react";

const WORKSPACE_PATH = "/workspace";

const steps = [
  { number: "01", title: "Upload a PDF", description: "Start with a report, invoice, contract, transcript, or any document." },
  { number: "02", title: "Choose the shape", description: "Use automatic extraction or provide a schema for a focused result." },
  { number: "03", title: "Review and export", description: "Inspect values and download structured data." },
];

function Logo() {
  return <a className="landing-logo" href="#top" aria-label="Document to Structured Data home"><span className="landing-logo-mark" aria-hidden="true"><FileText weight="fill" /></span><span>Document to Structured Data</span></a>;
}

function ButtonLink({ children, href, inverted = false }: { children: ReactNode; href: string; inverted?: boolean }) {
  return <a className={`landing-button${inverted ? " landing-button-inverted" : ""}`} href={href}>{children}<ArrowUpRight weight="bold" /></a>;
}

function Header() {
  return <header className="focus-header"><div className="landing-container focus-header-inner"><Logo /><div className="focus-header-actions"><ButtonLink href={WORKSPACE_PATH}>Open workspace</ButtonLink></div></div></header>;
}

function Hero() {
  return <section className="focus-hero" id="top"><div className="landing-container focus-hero-grid"><div className="focus-hero-copy"><p className="landing-kicker">PDF to structured data</p><h1>Extract structured data from every PDF.</h1><p className="landing-hero-description">Upload a document, define the fields you need, and review precise results.</p><div className="landing-button-row"><ButtonLink href={WORKSPACE_PATH}>Open workspace</ButtonLink><ButtonLink href="#how-it-works" inverted>See the workflow</ButtonLink></div><p className="focus-proof">Local-first workflow · confidence + citations</p></div><div className="focus-hero-art"><span className="focus-art-label">source / schema / output</span><img src="/document-flow.png" alt="PDF extraction flow from source document to structured output" /></div></div></section>;
}

function HowItWorks() {
  return <section className="focus-section focus-how" id="how-it-works"><div className="landing-container focus-how-grid"><div className="focus-how-copy"><p className="focus-eyebrow">How it works</p><h2>A direct path from document to usable data.</h2><div className="focus-step-list">{steps.map((step) => <div className="focus-step" key={step.number}><span>{step.number}</span><div><h3>{step.title}</h3><p>{step.description}</p></div></div>)}</div></div><div className="focus-workflow-art"><img src="/workflow-map.png" alt="Document extraction workflow diagram" /><div className="focus-art-caption"><FlowArrow /> parse, validate, export</div></div></div></section>;
}

function WorkspaceCta() {
  return <section className="focus-workspace-cta"><div className="landing-container focus-workspace-cta-inner"><div><p className="focus-eyebrow">Start with a document</p><h2>See your first structured result.</h2><p>Use the example PDF or upload your own document to explore the workflow.</p></div><ButtonLink href={WORKSPACE_PATH}>Open workspace</ButtonLink></div></section>;
}

export function ProductLanding() {
  useEffect(() => {
    const legacyWorkspaceLink = new URLSearchParams(window.location.search).get("workspace") === "1" || window.location.hash === "#workspace";
    if (legacyWorkspaceLink) window.location.replace(WORKSPACE_PATH);
  }, []);

  return <div className="landing-page"><Header /><main><Hero /><HowItWorks /><WorkspaceCta /></main></div>;
}
