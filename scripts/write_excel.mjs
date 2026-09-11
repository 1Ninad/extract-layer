import fs from "node:fs/promises";
import { pathToFileURL } from "node:url";

const nodeModules = process.env.PDF_LITPARSE_NODE_MODULES;
if (!nodeModules) {
  throw new Error("PDF_LITPARSE_NODE_MODULES is required for the bundled Excel writer");
}
const { SpreadsheetFile, Workbook } = await import(
  pathToFileURL(`${nodeModules}/@oai/artifact-tool/dist/artifact_tool.mjs`).href
);

function argument(name) {
  const index = process.argv.indexOf(name);
  if (index < 0 || !process.argv[index + 1]) {
    throw new Error(`Missing ${name}`);
  }
  return process.argv[index + 1];
}

function optionalArgument(name) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : undefined;
}

const mapping = JSON.parse(await fs.readFile(argument("--mapping-json"), "utf8"));
const outputPath = argument("--output-xlsx");
const previewPath = optionalArgument("--preview-png");
const workbook = Workbook.create();
const sheet = workbook.worksheets.add("Data");
const columns = mapping.columns;
const rows = mapping.rows;
const values = [columns, ...rows.map((row) => columns.map((column) => row[column] ?? ""))];
sheet.getRangeByIndexes(0, 0, values.length, columns.length).values = values;

if (previewPath) {
  const preview = await workbook.render({
    sheetName: "Data",
    range: `A1:T${Math.max(values.length, 1)}`,
    scale: 1,
    format: "png",
  });
  await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
}

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
try {
  await fs.unlink(`${outputPath}.inspect.ndjson`);
} catch (error) {
  if (error.code !== "ENOENT") throw error;
}
