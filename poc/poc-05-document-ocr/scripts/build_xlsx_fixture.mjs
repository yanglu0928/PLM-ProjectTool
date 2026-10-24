import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputPath = process.env.FINAL_XLSX;
if (!outputPath || !path.isAbsolute(outputPath)) {
  throw new Error("FINAL_XLSX must be an absolute path");
}

const workbook = Workbook.create();
const ledger = workbook.worksheets.add("项目台账");
const risks = workbook.worksheets.add("风险记录");
const font = "Microsoft YaHei";

ledger.showGridLines = false;
ledger.getRange("A2:D2").merge();
ledger.getRange("A2").values = [["POC 05 统一解析测试"]];
ledger.getRange("A2:D2").format = {
  font: { name: font, size: 14, bold: true, color: "#000000" },
  verticalAlignment: "center",
};
ledger.getRange("A4:D7").values = [
  ["项目编号", "项目名称", "里程碑", "状态"],
  ["PLM-2026-005", "PLM 项目实施辅助工具", "需求确认", "已完成"],
  ["PLM-2026-006", "文档解析验证", "客户确认", "进行中"],
  ["PLM-2026-007", "来源定位验证", "结果复核", "未开始"],
];
ledger.getRange("A4:D4").format = {
  fill: "#1F4E78",
  font: { name: font, size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  borders: { preset: "all", style: "thin", color: "#D9D9D9" },
};
ledger.getRange("A5:D7").format = {
  font: { name: font, size: 10, color: "#000000" },
  verticalAlignment: "center",
  borders: { preset: "all", style: "thin", color: "#D9D9D9" },
};
ledger.getRange("A6:D6").format.fill = "#EAF2F8";
ledger.getRange("A2:D7").format.autofitColumns();
ledger.getRange("A4:D7").format.autofitRows();
ledger.getRange("A:A").format.columnWidth = 18;
ledger.getRange("B:B").format.columnWidth = 28;
ledger.getRange("C:D").format.columnWidth = 16;
ledger.freezePanes.freezeRows(4);
ledger.tables.add("A4:D7", true, "ProjectLedgerTable");

risks.showGridLines = false;
risks.getRange("A2:C2").merge();
risks.getRange("A2").values = [["风险记录"]];
risks.getRange("A2:C2").format = {
  font: { name: font, size: 14, bold: true, color: "#000000" },
};
risks.getRange("A4:C6").values = [
  ["风险", "等级", "措施"],
  ["真实扫描件尚未提供", "中", "补充脱敏样本"],
  ["Debian 13 尚未验证", "高", "保留独立 Gate"],
];
risks.getRange("A4:C4").format = {
  fill: "#404040",
  font: { name: font, size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  borders: { preset: "all", style: "thin", color: "#D9D9D9" },
};
risks.getRange("A5:C6").format = {
  font: { name: font, size: 10, color: "#000000" },
  verticalAlignment: "center",
  borders: { preset: "all", style: "thin", color: "#D9D9D9" },
};
risks.getRange("A6:C6").format.fill = "#F2F2F2";
risks.getRange("A:C").format.autofitColumns();
risks.getRange("A:A").format.columnWidth = 30;
risks.getRange("B:B").format.columnWidth = 12;
risks.getRange("C:C").format.columnWidth = 24;
risks.tables.add("A4:C6", true, "RiskRegisterTable");

workbook.recalculate();
const inspect = await workbook.inspect({
  kind: "sheet,table",
  maxChars: 4000,
  tableMaxRows: 10,
  tableMaxCols: 8,
});
console.log(inspect.ndjson);
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const previewDir = process.env.PREVIEW_DIR;
if (previewDir) {
  await fs.mkdir(previewDir, { recursive: true });
  for (const sheetName of ["项目台账", "风险记录"]) {
    const preview = await workbook.render({ sheetName, autoCrop: "all", scale: 2, format: "png" });
    await fs.writeFile(
      path.join(previewDir, `${sheetName}.png`),
      new Uint8Array(await preview.arrayBuffer()),
    );
  }
}
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(outputPath);
