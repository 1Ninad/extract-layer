export type FieldType = "text" | "number" | "date" | "boolean";

export type FieldDefinition = {
  id: string;
  name: string;
  type: FieldType;
  description: string;
};

export type SchemaDefinition = {
  schema_version: 1;
  name: string;
  description: string;
  output_mode: "document" | "records";
  fields: Omit<FieldDefinition, "id">[];
  records?: {
    name: string;
    description: string;
    fields: Omit<FieldDefinition, "id">[];
  };
};

export type ExtractionResult = {
  source_file: string;
  schema: string;
  fields: Record<string, unknown>;
  records?: Record<string, unknown>[];
};

export type ExtractionResponse = {
  result: ExtractionResult;
  csv: string;
  page_count: number;
  elapsed_ms: number;
};
