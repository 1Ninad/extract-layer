export type FieldType = "text" | "number" | "date" | "boolean" | "array" | "object";

export type SchemaField = {
  name: string;
  type: FieldType;
  description: string;
  item_type?: FieldType;
};

export type SchemaDefinition = {
  schema_version: 1;
  name: string;
  description: string;
  output_mode: "document" | "records";
  fields: SchemaField[];
  records?: {
    name: string;
    description: string;
    fields: SchemaField[];
  };
};

export type ExtractionResponse = {
  job_id: string;
  source_file: string;
  result: {
    source_file: string;
    schema: string;
    fields: Record<string, string | number | boolean | null>;
    records?: Record<string, unknown>[];
  };
  csv: string;
  json_filename: string;
  csv_filename: string;
};
