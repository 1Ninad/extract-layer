export type FieldDefinition = {
  id: string;
  name: string;
  description: string;
};

export type SchemaFieldDefinition = {
  name: string;
  description: string;
  type?: "text" | "number" | "date" | "boolean" | "array" | "object";
};

export type SchemaDefinition = {
  schema_version: 1;
  name: string;
  description: string;
  fields: SchemaFieldDefinition[];
  table?: {
    name: string;
    description: string;
    fields: SchemaFieldDefinition[];
  };
};

export type ExtractionMode = "automatic" | "schema";

export type SchemaUploadState = {
  fileName: string;
  raw: string;
  schema: SchemaDefinition;
};

export type AutomaticField = {
  label: string;
  value: string;
  confidence: number;
  evidence: string[];
  status: "accepted" | "empty";
  source?: Record<string, unknown>;
};

export type AutomaticTable = {
  id: string;
  name: string;
  pages: number[];
  duplicate_pages?: number[];
  columns: string[];
  row_count?: number;
  column_count?: number;
  header_rows: string[][];
  rows: Record<string, string>[];
  grid: string[][];
  cells: Array<Array<Record<string, unknown> | null>>;
  bbox: Record<string, number> | null;
  bboxes?: Array<{ page: number | null; bbox: Record<string, number> | null }>;
  confidence: number;
  status: "accepted" | "review";
};

export type AutomaticReviewItem = {
  label?: string;
  value?: string;
  text?: string;
  markdown?: string;
  coordinates?: string[];
  reason: string;
  page?: number;
  source?: Record<string, unknown>;
};

export type AutomaticExtractionResult = {
  source_file: string;
  mode: "automatic";
  fields: AutomaticField[];
  tables: AutomaticTable[];
  unlabeled: AutomaticReviewItem[];
  review: AutomaticReviewItem[];
  deduplication?: {
    identical_fields_collapsed: number;
    identical_table_copies_collapsed: number;
  };
  mapping: { markdown: boolean; coordinates: boolean; llm: false };
};

export type LegacyExtractionResult = {
  source_file: string;
  schema: string;
  fields: Record<string, unknown>;
  records?: Record<string, unknown>[];
  table?: {
    name: string;
    description: string;
    columns: string[];
    rows: Record<string, unknown>[];
  };
};

export type ExtractionResult = AutomaticExtractionResult | LegacyExtractionResult;

export type ExtractionResponse = {
  result: ExtractionResult;
  csv: string;
  page_count: number;
  elapsed_ms: number;
  processing: {
    mode: "automatic" | "automatic_ocr_requested" | "automatic_ocr_fallback" | "native" | "ocr_requested" | "ocr_fallback";
    ocr_used: boolean;
    note: string;
  };
};
