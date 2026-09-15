import { NextResponse } from "next/server";

import { examplePdfBase64 } from "@/lib/example-data";

export const dynamic = "force-dynamic";

export async function GET() {
  const pdf = Buffer.from(examplePdfBase64, "base64");

  return new NextResponse(pdf, {
    headers: {
      "Cache-Control": "public, max-age=3600",
      "Content-Type": "application/pdf",
      "Content-Length": String(pdf.byteLength),
    },
  });
}
