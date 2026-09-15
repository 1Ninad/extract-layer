import { PlusIcon, TrashIcon } from "./icons";
import type { FieldDefinition, FieldType } from "@/lib/types";

type Props = {
  schemaName: string;
  description: string;
  outputMode: "document" | "records";
  fields: FieldDefinition[];
  recordFields: FieldDefinition[];
  disabled: boolean;
  onSchemaName: (value: string) => void;
  onDescription: (value: string) => void;
  onOutputMode: (value: "document" | "records") => void;
  onFields: (value: FieldDefinition[]) => void;
  onRecordFields: (value: FieldDefinition[]) => void;
};

const types: FieldType[] = ["text", "number", "date", "boolean"];

function newField(): FieldDefinition {
  return { id: crypto.randomUUID(), name: "", type: "text", description: "" };
}

function FieldRows({ fields, onChange, disabled }: { fields: FieldDefinition[]; onChange: (fields: FieldDefinition[]) => void; disabled: boolean }) {
  const update = (id: string, patch: Partial<FieldDefinition>) => onChange(fields.map((field) => field.id === id ? { ...field, ...patch } : field));
  return (
    <div className="field-list">
      <div className="field-labels"><span>Field name</span><span>Type</span><span>Description</span><span /></div>
      {fields.map((field) => (
        <div className="field-row" key={field.id}>
          <input aria-label="Field name" value={field.name} disabled={disabled} onChange={(event) => update(field.id, { name: event.target.value })} placeholder="e.g. invoice_number" />
          <select aria-label={`Type for ${field.name || "field"}`} value={field.type} disabled={disabled} onChange={(event) => update(field.id, { type: event.target.value as FieldType })}>
            {types.map((type) => <option key={type}>{type}</option>)}
          </select>
          <input aria-label={`Description for ${field.name || "field"}`} value={field.description} disabled={disabled} onChange={(event) => update(field.id, { description: event.target.value })} placeholder="How to identify this value" />
          <button className="icon-button" type="button" disabled={disabled || fields.length === 1} onClick={() => onChange(fields.filter((item) => item.id !== field.id))} aria-label={`Remove ${field.name || "field"}`}><TrashIcon /></button>
        </div>
      ))}
      <button className="text-button" type="button" disabled={disabled} onClick={() => onChange([...fields, newField()])}><PlusIcon /> Add field</button>
    </div>
  );
}

export function SchemaBuilder(props: Props) {
  return (
    <section className="panel schema-panel" aria-labelledby="schema-title">
      <div className="panel-heading"><div><h2 id="schema-title">Schema configuration</h2><p>Describe only values that appear in the document.</p></div></div>
      <div className="schema-meta">
        <label>Schema name<input value={props.schemaName} disabled={props.disabled} onChange={(event) => props.onSchemaName(event.target.value)} /></label>
        <label>Document description<textarea rows={2} value={props.description} disabled={props.disabled} onChange={(event) => props.onDescription(event.target.value)} /></label>
      </div>
      <fieldset className="mode-fieldset" disabled={props.disabled}>
        <legend>Output mode</legend>
        <label className={props.outputMode === "document" ? "mode active" : "mode"}><input type="radio" name="mode" checked={props.outputMode === "document"} onChange={() => props.onOutputMode("document")} /><span><strong>Document</strong><small>One row per PDF</small></span></label>
        <label className={props.outputMode === "records" ? "mode active" : "mode"}><input type="radio" name="mode" checked={props.outputMode === "records"} onChange={() => props.onOutputMode("records")} /><span><strong>Records</strong><small>Repeated rows or items</small></span></label>
      </fieldset>
      <div className="field-section"><h3>Document fields</h3><FieldRows fields={props.fields} onChange={props.onFields} disabled={props.disabled} /></div>
      {props.outputMode === "records" ? <div className="field-section records-section"><div><h3>Record fields</h3><p>One output row for every matching item.</p></div><FieldRows fields={props.recordFields} onChange={props.onRecordFields} disabled={props.disabled} /></div> : null}
    </section>
  );
}
