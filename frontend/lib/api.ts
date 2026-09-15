import type { ExtractionResponse, SchemaDefinition } from "../types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function checkHealth() {
  const response = await fetch(`${API_URL}/api/health`, { cache: "no-store" });
  if (!response.ok) throw new Error("API is unavailable");
  return response.json() as Promise<{ status: string; pipeline: string }>;
}

export async function extractPdf(file: File, schema: SchemaDefinition, ocr: boolean) {
  const form = new FormData();
  form.append("file", file);
  form.append("schema", JSON.stringify(schema));
  form.append("ocr", String(ocr));
  const response = await fetch(`${API_URL}/api/extract`, { method: "POST", body: form });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || "Extraction failed.");
  return payload as ExtractionResponse;
}
