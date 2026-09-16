export const exampleSchema = {
  schema_version: 1,
  name: "certificate_of_quality",
  description:
    "Extract the requested certificate-level identifiers and the characteristic results listed under each batch. Preserve every value exactly as printed in the source PDF.",
  output_mode: "records",
  fields: [
    {
      name: "company_name",
      type: "text",
      description:
        "Company name: the issuing company shown in the certificate header or footer, not the recipient or packaging-group name.",
    },
    {
      name: "country",
      type: "text",
      description:
        "Country: the country in the issuing company's address or footer, not the state or city.",
    },
    {
      name: "reference_code",
      type: "text",
      description:
        "Reference Code: the exact value printed next to Certificate No.; do not use the order, shipment, customer, or invoice number.",
    },
    {
      name: "issued_on",
      type: "date",
      description:
        "Issued On: the exact date printed next to Issue Date, preserving the source formatting.",
    },
    {
      name: "order_number",
      type: "text",
      description:
        "Order Number: the complete exact value printed next to Order Ref., including any date after a slash; do not use a batch, shipment, customer, or invoice number.",
    },
    {
      name: "consignment_number",
      type: "text",
      description:
        "Consignment Number: the complete exact value printed next to Shipment Ref., including any date after a slash; do not use the order or customer number.",
    },
    {
      name: "client_id",
      type: "text",
      description:
        "Client ID: the exact value printed next to Customer Code.",
    },
  ],
  records: {
    name: "test_results",
    description:
      "One record for every characteristic row in every batch table. For each row, copy the lot number from the nearest preceding Batch (Lot) line. Include only the requested fields below; ignore Min and Max columns and other batch metadata such as expiry date, quantity, and manufacture date.",
    fields: [
      {
        name: "lot_number",
        type: "text",
        description:
          "Lot Number: the exact value immediately following Batch (Lot) for the batch containing this characteristic row; do not include the expiry date, quantity, or manufacture date.",
      },
      {
        name: "characteristic",
        type: "text",
        description:
          "Characteristic: the exact text from the Property column for this row, such as Melt Flow Index (190C/2.16kg), Density, or Contamination (Fluorescence).",
      },
      {
        name: "unit",
        type: "text",
        description:
          "Unit: the exact value from the Unit column for this characteristic row.",
      },
      {
        name: "result",
        type: "text",
        description:
          "Result: the exact value from the Result column for this characteristic row, including comparison symbols, spaces, punctuation, and trailing zeroes; never substitute Min or Max.",
      },
      {
        name: "test_method",
        type: "text",
        description:
          "Test Method: the exact value from the Test Method column for this characteristic row.",
      },
    ],
  },
} as const;

// Keep this sample aligned with examples/input.json and examples/input.pdf.
export const examplePdfBase64 = "JVBERi0xLjQKJZOMi54gUmVwb3J0TGFiIEdlbmVyYXRlZCBQREYgZG9jdW1lbnQgKG9wZW5zb3VyY2UpCjEgMCBvYmoKPDwKL0YxIDIgMCBSIC9GMiAzIDAgUgo+PgplbmRvYmoKMiAwIG9iago8PAovQmFzZUZvbnQgL0hlbHZldGljYSAvRW5jb2RpbmcgL1dpbkFuc2lFbmNvZGluZyAvTmFtZSAvRjEgL1N1YnR5cGUgL1R5cGUxIC9UeXBlIC9Gb250Cj4+CmVuZG9iagozIDAgb2JqCjw8Ci9CYXNlRm9udCAvSGVsdmV0aWNhLUJvbGQgL0VuY29kaW5nIC9XaW5BbnNpRW5jb2RpbmcgL05hbWUgL0YyIC9TdWJ0eXBlIC9UeXBlMSAvVHlwZSAvRm9udAo+PgplbmRvYmoKNCAwIG9iago8PAovQ29udGVudHMgOCAwIFIgL01lZGlhQm94IFsgMCAwIDYxMiA3OTIgXSAvUGFyZW50IDcgMCBSIC9SZXNvdXJjZXMgPDwKL0ZvbnQgMSAwIFIgL1Byb2NTZXQgWyAvUERGIC9UZXh0IC9JbWFnZUIgL0ltYWdlQyAvSW1hZ2VJIF0KPj4gL1JvdGF0ZSAwIC9UcmFucyA8PAoKPj4gCiAgL1R5cGUgL1BhZ2UKPj4KZW5kb2JqCjUgMCBvYmoKPDwKL1BhZ2VNb2RlIC9Vc2VOb25lIC9QYWdlcyA3IDAgUiAvVHlwZSAvQ2F0YWxvZwo+PgplbmRvYmoKNiAwIG9iago8PAovQXV0aG9yIChcKGFub255bW91c1wpKSAvQ3JlYXRpb25EYXRlIChEOjIwMjYwOTE0MTEzNzQwKzAwJzAwJykgL0NyZWF0b3IgKFwodW5zcGVjaWZpZWRcKSkgL0tleXdvcmRzICgpIC9Nb2REYXRlIChEOjIwMjYwOTE0MTEzNzQwKzAwJzAwJykgL1Byb2R1Y2VyIChSZXBvcnRMYWIgUERGIExpYnJhcnkgLSBcKG9wZW5zb3VyY2VcKSkgCiAgL1N1YmplY3QgKFwodW5zcGVjaWZpZWRcKSkgL1RpdGxlIChcKGFub255bW91c1wpKSAvVHJhcHBlZCAvRmFsc2UKPj4KZW5kb2JqCjcgMCBvYmoKPDwKL0NvdW50IDEgL0tpZHMgWyA0IDAgUiBdIC9UeXBlIC9QYWdlcwo+PgplbmRvYmoKOCAwIG9iago8PAovRmlsdGVyIFsgL0FTQ0lJODVEZWNvZGUgL0ZsYXRlRGVjb2RlIF0gL0xlbmd0aCAyMTI3Cj4+CnN0cmVhbQpHYiIvKDk2OGlHJkFKJENtJWxMMS1EQ1AxImEjJ0lEKWxfaDU4I2JIMVpKajlfJUw3NzwoU1FyQkRVWiMsUVgoNiN1YmwtbCh1dGAxcTRWQ10qbXVuOCEqa2gmJD5oIy50RkFwJVNuTk0jL01sZmEpVztpX0JfLDlxZ14vbGs/PmZIJmA/VT5FXUM9RCpmPE44Y0s1QDgiMCIsXWE3RFVBWVVIM15VTDtkP2w/XkQzTm1eMzRfcEYmT1dhbkE/V0tMNzI4Jm89QVVqMztLbDEwOUxaaHN0MFQtL0FdWTRXUHBtPFshTyg4W09RczRHXTQ3QF9NPD83dDc3KDNjYkBVLStoJU90blFJZ0dmTkokMGElU2gxV3RdXENWK0xcJ14wVURdZFdsMSE6NShUS1U1dVcnYClBXGNBKCFTNVYmVSxITHE0J2pzZytHZnJKOlBxTFlfRy51TjdVWFNfOS9BO0tuRSJ0aWRpQjBsdG4wVWRlbGNRdWpfOXE/Zzo+PTFuLFZKLWRYcFlaWSVhaW10bWNyJ1JeOiZMXC9bbWJuR2ViZ0dbZUFaKFs1cip0bTRHX19iQjVQckhNMGNdLUgpVTpwbW1nS2dYVmJOUD1pciJTbzVtRVRFVnMxWHNSJSlJX0QvMSkuREFYPGQxVFMza0VPSTE0c2ZBRyVdXl9gMmgoZGJMKEFqIkBCbEImPVpidFhyJFZTLSdNZGs+UC1dWFk6c04tPXJLY01baHIlRUtROlFdSCcpUGJKRShhW289IWtubiNxP3UtJyVrbXAkNltBUUApSGZCV2kpSy09NlUpKDUsUT1SRltaNUEsMSlTQ1M8KkZZXkVlWGhlaUUpQ0ksRURZWGJQSio3JmFDTEonVWhIJ0g7NiwjND5vLyprcCswblNIRGNnZ1hcaUddNFNiN0FQSVxbWGcyNS9QazNvXSU0bHAjQy43MGVxNzVlay5KKV4yUnFxKW4rVygqazRNLFZ1OFJeTWVFLE1VTTNvZV1dYUtHSDg8PVhxbF4jTWt0IytaZmJ1O0pdPkE3UEZXRyxoPFc1M2BnU1FzZjtfPDBXVXFpO2U9PTdVXiNVL143UmxyWCNMV1NbOk4vQz1WSGBhRCJIJS9PRG0/YGYsJCUnZEhtRDwxSSQwMjlKJjVVS1NnJ10pYUVQTjMxcTFEYjBIZCIvNytYczw0YzY6c21TKSJvYy9mSyQ0bmowJFw6R2k4SWg3QmIja28tJi5JRTI4J145Ty00MiI3ZW4pNStdVitVUlpYa1c+Mk5RM0skUTUmcU0mMXVSc2IwZChtTiJmMjZTP2ksQzQnQTJrRU1bWC0mXnB1ITNsImteZDVjWVRKXW9aSjdFNFNgWF5mYEZWP1NOQHErTks4SUwjMVlgayhPcmEyUi4nO3BJJEh1KyZdQyJcT0pVLSpvXSUtVTIiLUNLJD5sYic7Z20razhCQGQrSTBmLWRIR1pcYTxrNCNxPiotM0xELFA8cCNFPC5NW0ZcUVA8OmBFKGJGJSptZydBbyslQGQ4ak0jRT9TMkdWTC0oIl9VQ3NWWy5hMT4pVyEuO3QiSnAzcFY1UWhlLk5kcmRNLjAvIzlvWjhMQWhHa0lBVklYV29MN29sZW9vcnJiI2UyMC9EX3REYSE+KFE5WWlCSUAxJGZNZGtjajdAPGhtTCNgZCVfTTk8YENeZlhVYzVWQEEpZFg1KFFKWWBxW2UxUlpJRiJiWyUhQU1VblNTSTNdSypAQ0ZObztjZ1EsbnBuNFVDP2lULkE7bUopRzE8cW9NIT1RLTQzbHQjZ10iUVhLRkNEQVheaVxaSUtLKSFLUkRYNy1LSWwlMyxgWkYsXGVUTytkY1ZaVSxgQSJhJlJvJjFISUUjalVESDUjUiw7a2lzO0dOKSNfLzFkX0htUD1RVS1WJS83W0Y9XU9TLHFAQ3Q1YEApLUVAbzBiKGM/Pk1NP0Z0N2hyYj8jamEqamIlJj9ESGFGRCtiOklgZTBtTD4nMzlATEBPOiQ0LSE5PVYsTVVpVy9FaCdGKEhNcy9jRUtxVSQ1T2Q6Z2snW2EpQVpkKnQ9a2trLzFlKSYscl4ySjM5WVdGQFIvWmRSIzw3RCZGPmVNI14oL3BqVFhKKGdDNXE/VCxlalEzcjJoUi5HWTtvVC88cl1YLFMoW0hdUUp1TUxqaTZIY0N1RnVNW3UiNUFUJWE2byZAISFAaGolOypoaysiTHJsWTFaYDdpbXM9UEwhXyovQVNbWlkhTU8obzVgTSlySlQ4J3E8ajw9PWEiUl1OUUomVT1CVDRhSnErOE9BbWFnRiNlQXUzQmEhNS5qX2ZJQydEVWREZFwmKEpeQCkpUXI+cSkjPEIxWSVXY0MoMWo3cC8kRzZiRTxtWyQuKUA7WWZlL2RgYVZzWmcqMzsiJkBIQGYnR1QhOGcoPGA9YDRbPVRSPmZTciEmRih1LihqTz1PSCxIKE81NkxANDg5TFMibCFuRypfcHNYXmRMNzc2JFxQT089VmFATXFMQyNpVElOa1QrN05US1EvOU1GV0lvIjMsQVZDXm0qV1pFdV1nJCEhcWtOUTExOD4/bVUsOUU/WlA9L15JJlxZMycoWDpuXW87JV08ci0lT1EnPV5EYkxTR0toZVpdc2o6S1RtTTg3QFNGIis2Km8rLlRlWSk8anRhVm5iKlhGLU5QTmJgZnNbIihIX2xHY0FAP2JYPm5iKlBLIUAoMkloTjwqIUBkc3RnPGs3RGRtIjYhJy9BUTMyU0ppQiI9SGI+UFxkJC01UF88NWJUY2VxSFQpN3E9P082OVc7T0xSRl4rV1VDZlojUCJKfj5lbmRzdHJlYW0KZW5kb2JqCnhyZWYKMCA5CjAwMDAwMDAwMDAgNjU1MzUgZiAKMDAwMDAwMDA2MSAwMDAwMCBuIAowMDAwMDAwMTAyIDAwMDAwIG4gCjAwMDAwMDAyMDkgMDAwMDAgbiAKMDAwMDAwMDMyMSAwMDAwMCBuIAowMDAwMDAwNTE0IDAwMDAwIG4gCjAwMDAwMDA1ODIgMDAwMDAgbiAKMDAwMDAwMDg2MiAwMDAwMCBuIAowMDAwMDAwOTIxIDAwMDAwIG4gCnRyYWlsZXIKPDwKL0lEIApbPGYxNzFmYjRmZWIxYWRkM2FhZTJlMDI0OTQ2NTQ1ZDMwPjxmMTcxZmI0ZmViMWFkZDNhYWUyZTAyNDk0NjU0NWQzMD5dCiUgUmVwb3J0TGFiIGdlbmVyYXRlZCBQREYgZG9jdW1lbnQgLS0gZGlnZXN0IChvcGVuc291cmNlKQoKL0luZm8gNiAwIFIKL1Jvb3QgNSAwIFIKL1NpemUgOQo+PgpzdGFydHhyZWYKMzEzOQolJUVPRgo=";
