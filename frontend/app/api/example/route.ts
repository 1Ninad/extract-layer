import { NextResponse } from "next/server";

import { exampleSchema } from "@/lib/example-data";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json({
    filename: "input.pdf",
    pdf_url: "/api/example/pdf",
    schema: exampleSchema,
  });
}
