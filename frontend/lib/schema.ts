import type { SchemaDefinition, SchemaFieldDefinition, SchemaUploadState } from "./types";

export const MAX_SCHEMA_BYTES = 1024 * 1024;

const FIELD_TYPES = new Set(["text", "number", "date", "boolean", "array", "object"]);

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function requireText(value: unknown, label: string): string {
  if (typeof value !== "string" || !value.trim()) throw new Error(`${label} must be a non-empty string.`);
  return value;
}

function parseFields(value: unknown, label: string): SchemaFieldDefinition[] {
  if (!Array.isArray(value)) throw new Error(`${label} must be an array.`);
  return value.map((item, index) => {
    if (!isObject(item)) throw new Error(`${label}[${index}] must be an object.`);
    const field: SchemaFieldDefinition = {
      name: requireText(item.name, `${label}[${index}].name`),
      description: requireText(item.description, `${label}[${index}].description`),
    };
    if (item.type !== undefined) {
      if (typeof item.type !== "string" || !FIELD_TYPES.has(item.type)) {
        throw new Error(`${label}[${index}].type must be text, number, date, boolean, array, or object.`);
      }
      field.type = item.type as SchemaFieldDefinition["type"];
    }
    return field;
  });
}

export function parseSchema(raw: unknown): SchemaDefinition {
  if (!isObject(raw)) throw new Error("The schema file must contain a JSON object.");
  if (raw.schema_version !== 1) throw new Error("schema_version must be 1.");
  const schema: SchemaDefinition = {
    schema_version: 1,
    name: requireText(raw.name, "name"),
    description: requireText(raw.description, "description"),
    fields: parseFields(raw.fields, "fields"),
  };

  if (raw.table !== undefined) {
    if (!isObject(raw.table)) throw new Error("table must be an object.");
    schema.table = {
      name: requireText(raw.table.name, "table.name"),
      description: requireText(raw.table.description, "table.description"),
      fields: parseFields(raw.table.fields, "table.fields"),
    };
  }

  if (!schema.fields.length && !schema.table?.fields.length) {
    throw new Error("Add at least one document field or table field.");
  }

  const names = [...schema.fields, ...(schema.table?.fields || [])].map((field) => field.name);
  if (new Set(names).size !== names.length) throw new Error("Field names must be unique across the document and table.");
  return schema;
}

export async function readSchemaFile(file: File): Promise<SchemaUploadState> {
  if (!file.name.toLowerCase().endsWith(".json")) throw new Error("Choose a JSON schema file.");
  if (file.size > MAX_SCHEMA_BYTES) throw new Error("Schema files must be smaller than 1 MB.");
  let parsed: unknown;
  try {
    parsed = JSON.parse(await file.text());
  } catch {
    throw new Error("The schema file is not valid JSON.");
  }
  const schema = parseSchema(parsed);
  return { fileName: file.name, raw: JSON.stringify(schema), schema };
}

export function schemaSummary(schema: SchemaDefinition): string {
  const fieldCount = schema.fields.length;
  if (!schema.table) return `${fieldCount} document field${fieldCount === 1 ? "" : "s"}`;
  return `${fieldCount} document field${fieldCount === 1 ? "" : "s"} and ${schema.table.fields.length} table field${schema.table.fields.length === 1 ? "" : "s"}`;
}

export const exampleSchema: SchemaDefinition = {
  schema_version: 1,
  name: "invoice",
  description: "Extract invoice details and line items.",
  fields: [
    { name: "invoice_number", description: "The printed invoice number." },
    { name: "invoice_date", description: "The printed invoice date." },
  ],
  table: {
    name: "line_items",
    description: "Each product or service row.",
    fields: [
      { name: "description", description: "The product or service description." },
      { name: "quantity", description: "The printed quantity." },
    ],
  },
};
