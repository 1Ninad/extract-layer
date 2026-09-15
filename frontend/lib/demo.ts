import type { ExtractionResponse } from "./types";

export const demoResponse: ExtractionResponse = {
  page_count: 1,
  elapsed_ms: 18342,
  csv: "source_file,company_name,country,reference_code,issued_on,order_number,consignment_number,client_id,lot_number,characteristic,unit,result,test_method\ninput.pdf,Contoso Polymers,United States,CNT-0041207,12-Aug-2026,PO-58120 / 01-Aug-2026,SHP-77410 / 10-Aug-2026,CUST-10456,CTXLDE0217A,Density,g/cm3,0.923,ASTM D792\n",
  result: {
    source_file: "input.pdf",
    schema: "certificate_of_quality",
    fields: {
      company_name: "Contoso Polymers",
      country: "United States",
      reference_code: "CNT-0041207",
      issued_on: "12-Aug-2026",
      order_number: "PO-58120 / 01-Aug-2026",
      consignment_number: "SHP-77410 / 10-Aug-2026",
      client_id: "CUST-10456",
    },
    records: [
      { lot_number: "CTXLDE0217A", characteristic: "Melt Flow Index (190C/2.16kg)", unit: "g/10min", result: "2.10", test_method: "ASTM D1238" },
      { lot_number: "CTXLDE0217A", characteristic: "Density", unit: "g/cm3", result: "0.923", test_method: "ASTM D792" },
      { lot_number: "CTXLDE0217A", characteristic: "Melting Point", unit: "C", result: "110", test_method: "Internal Method" },
      { lot_number: "CTXLDE0217A", characteristic: "Tensile Strength at Break", unit: "MPa", result: "14.2", test_method: "ASTM D638" },
      { lot_number: "CTXLDE0219B", characteristic: "Contamination (Fluorescence)", unit: "%", result: "< 0.2", test_method: "Internal Method" },
    ],
  },
};
