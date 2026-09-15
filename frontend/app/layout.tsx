import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DocuTable — Document to database",
  description: "Extract structured data from a PDF using a schema you control.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
