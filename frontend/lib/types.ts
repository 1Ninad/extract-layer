export type FieldDefinition = {
  id: string;
  name: string;
  description: string;
};

type SchemaField = Omit<FieldDefinition, "id"> & { type: "text" };

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
  processing: {
    mode: "native" | "ocr_requested" | "ocr_fallback";
    ocr_used: boolean;
    note: string;
  };
};
