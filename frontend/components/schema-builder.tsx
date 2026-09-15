import { Cross2Icon, PlusIcon } from "@radix-ui/react-icons";
import type { FieldDefinition } from "@/lib/types";

type Props = {
  schemaName: string;
  description: string;
  outputMode: "document" | "records";
  fields: FieldDefinition[];
  recordFields: FieldDefinition[];
  disabled: boolean;
  visible: boolean;
  onSchemaName: (value: string) => void;
  onDescription: (value: string) => void;
  onOutputMode: (value: "document" | "records") => void;
  onFields: (value: FieldDefinition[]) => void;
  onRecordFields: (value: FieldDefinition[]) => void;
};

function newField(): FieldDefinition {
  return { id: crypto.randomUUID(), name: "", description: "" };
}

function FieldEditor({ fields, disabled, onChange }: { fields: FieldDefinition[]; disabled: boolean; onChange: (fields: FieldDefinition[]) => void }) {
  const update = (id: string, value: Partial<FieldDefinition>) => onChange(fields.map((field) => field.id === id ? { ...field, ...value } : field));
  return (
    <div className="field-editor">
      <div className="field-editor-labels"><span>Field name</span><span>Description</span><span /></div>
      {fields.map((field) => (
        <div className="schema-field-row" key={field.id}>
          <input aria-label="Field name" value={field.name} disabled={disabled} placeholder="Field name" onChange={(event) => update(field.id, { name: event.target.value })} />
          <input aria-label={`Description for ${field.name || "field"}`} value={field.description} disabled={disabled} placeholder="How this value appears in the PDF" onChange={(event) => update(field.id, { description: event.target.value })} />
          <button className="icon-button" type="button" disabled={disabled || fields.length === 1} aria-label={`Remove ${field.name || "field"}`} onClick={() => onChange(fields.filter((item) => item.id !== field.id))}><Cross2Icon /></button>
        </div>
      ))}
      <button className="add-field-button" type="button" disabled={disabled} onClick={() => onChange([...fields, newField()])}><PlusIcon /> Add field</button>
    </div>
  );
}

export function SchemaBuilder(props: Props) {
  return (
    <section className={`workspace-pane data-pane ${props.visible ? "mobile-visible" : ""}`} aria-labelledby="schema-heading">
      <header className="pane-header"><div><span className="pane-kicker">Schema</span><h2 id="schema-heading">Describe the values you need</h2><p>Give each field a name and a short description.</p></div></header>
      <div className="schema-scroll">
        <div className="schema-meta">
          <label>Schema name<input value={props.schemaName} placeholder="e.g. invoice" disabled={props.disabled} onChange={(event) => props.onSchemaName(event.target.value)} /></label>
          <label>Document description<textarea rows={3} value={props.description} placeholder="e.g. Extract the invoice number and issue date." disabled={props.disabled} onChange={(event) => props.onDescription(event.target.value)} /></label>
        </div>
        <fieldset className="mode-switch" disabled={props.disabled}>
          <legend>Output structure</legend>
          <button type="button" className={props.outputMode === "document" ? "active" : ""} onClick={() => props.onOutputMode("document")}><strong>Document</strong><span>One output row</span></button>
          <button type="button" className={props.outputMode === "records" ? "active" : ""} onClick={() => props.onOutputMode("records")}><strong>Records</strong><span>Repeat table rows or items</span></button>
        </fieldset>
        <section className="schema-section"><div className="section-heading"><h3>Document fields</h3><span>{props.fields.length}</span></div><FieldEditor fields={props.fields} disabled={props.disabled} onChange={props.onFields} /></section>
        {props.outputMode === "records" ? <section className="schema-section"><div className="section-heading"><div><h3>Record fields</h3><p>One record for every matching repeated item.</p></div><span>{props.recordFields.length}</span></div><FieldEditor fields={props.recordFields} disabled={props.disabled} onChange={props.onRecordFields} /></section> : null}
      </div>
    </section>
  );
}
