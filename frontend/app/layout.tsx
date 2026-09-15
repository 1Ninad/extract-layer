import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Document to Database",
  description: "Extract schema-defined data from PDFs.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
