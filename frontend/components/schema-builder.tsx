import { Cross2Icon, PlusIcon } from "@/components/icons";
import type { FieldDefinition } from "@/lib/types";

type Props = {
  schemaName: string;
  description: string;
  outputMode: "document" | "records";
  fields: FieldDefinition[];
  recordFields: FieldDefinition[];
  tableName: string;
  tableDescription: string;
  disabled: boolean;
  visible: boolean;
  error: string;
  validating: boolean;
  onSchemaName: (value: string) => void;
  onDescription: (value: string) => void;
  onOutputMode: (value: "document" | "records") => void;
  onFields: (value: FieldDefinition[]) => void;
  onRecordFields: (value: FieldDefinition[]) => void;
  onTableName: (value: string) => void;
  onTableDescription: (value: string) => void;
  onSave: () => void;
};

function newField(): FieldDefinition {
  return { id: crypto.randomUUID(), name: "", description: "" };
}

function FieldEditor({ fields, disabled, onChange }: { fields: FieldDefinition[]; disabled: boolean; onChange: (fields: FieldDefinition[]) => void }) {
  const update = (id: string, value: Partial<FieldDefinition>) => onChange(fields.map((field) => field.id === id ? { ...field, ...value } : field));
  return (
    <div className="field-editor">
      <div className="field-editor-labels"><span>What should we call it?</span><span>How will it appear?</span><span /></div>
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
    <section className={`workspace-pane data-pane schema-builder-pane ${props.visible ? "mobile-visible" : ""}`} aria-labelledby="schema-heading">
      <div className="schema-scroll">
        <div className="schema-meta">
          <label>Give this extraction a name<input value={props.schemaName} placeholder="e.g. Invoice details" disabled={props.disabled} onChange={(event) => props.onSchemaName(event.target.value)} /></label>
          <label>What should we look for in this PDF?<textarea rows={3} value={props.description} placeholder="e.g. Find the invoice number, issue date, and totals." disabled={props.disabled} onChange={(event) => props.onDescription(event.target.value)} /></label>
        </div>
        <fieldset className="mode-switch" disabled={props.disabled}>
          <legend>What kind of information is in this PDF?</legend>
          <button type="button" className={props.outputMode === "document" ? "active" : ""} onClick={() => props.onOutputMode("document")}><strong>Details from each PDF</strong><span>For information that appears once, like an invoice number or date.</span></button>
          <button type="button" className={props.outputMode === "records" ? "active" : ""} onClick={() => props.onOutputMode("records")}><strong>Rows from a repeated list</strong><span>For line items, products, people, or other repeated entries.</span></button>
        </fieldset>
        <section className="schema-section"><div className="section-heading"><div><h3>Details to extract from the PDF</h3><p>Add each value you want in the result.</p></div><span>{props.fields.length}</span></div><FieldEditor fields={props.fields} disabled={props.disabled} onChange={props.onFields} /></section>
        {props.outputMode === "records" ? <section className="schema-section"><div className="section-heading"><div><h3>Details in each repeated row</h3><p>These become one result row for every matching item.</p></div><span>{props.recordFields.length}</span></div><div className="schema-meta"><label>What should we call this list?<input value={props.tableName} placeholder="e.g. Products or line items" disabled={props.disabled} onChange={(event) => props.onTableName(event.target.value)} /></label><label>What does each row represent?<textarea rows={2} value={props.tableDescription} placeholder="e.g. Each product or service on the invoice." disabled={props.disabled} onChange={(event) => props.onTableDescription(event.target.value)} /></label></div><FieldEditor fields={props.recordFields} disabled={props.disabled} onChange={props.onRecordFields} /></section> : null}
        <div className="schema-builder-actions"><button className="primary-button" type="button" disabled={props.disabled} onClick={props.onSave}>{props.validating ? "Checking and extracting..." : "Extract from this PDF"}</button>{props.error ? <p className="schema-inline-error" role="alert">{props.error}</p> : null}</div>
      </div>
    </section>
  );
}
