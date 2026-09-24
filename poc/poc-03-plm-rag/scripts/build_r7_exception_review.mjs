import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const packagePath = process.argv[2];
const outputDir = process.argv[3];
if (!packagePath || !outputDir) {
  throw new Error("Usage: node build_r7_exception_review.mjs <exception-package.json> <output-dir>");
}

const reviewPackage = JSON.parse(await fs.readFile(packagePath, "utf8"));
const item = reviewPackage.case;
if (!item?.case_id || !item?.proposed_query || !item?.proposed_classification) {
  throw new Error("Exception package is incomplete");
}

const FONT = "Microsoft YaHei";
const COLORS = {
  navy: "#17365D",
  blue: "#1F4E78",
  paleBlue: "#D9EAF7",
  amber: "#FFF2CC",
  amberStrong: "#FFD966",
  green: "#E2F0D9",
  red: "#FCE4D6",
  redText: "#9C0006",
  border: "#B4C6E7",
  text: "#1F2937",
};

function header(range) {
  range.format = {
    fill: COLORS.navy,
    font: { name: FONT, size: 10, bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "all", style: "thin", color: "#FFFFFF" },
    rowHeight: 38,
  };
}

function body(range) {
  range.format = {
    font: { name: FONT, size: 10, color: COLORS.text },
    verticalAlignment: "top",
    wrapText: true,
    borders: { preset: "all", style: "thin", color: COLORS.border },
  };
}

const workbook = Workbook.create();
const review = workbook.worksheets.add("R7.1确认");
const evidence = workbook.worksheets.add("证据说明");
review.showGridLines = false;
evidence.showGridLines = false;
review.tabColor = COLORS.navy;
evidence.tabColor = "#70AD47";

review.mergeCells("A2:J2");
review.getRange("A2").values = [["POC-03 Golden R7.1 · 非标准覆盖例外确认"]];
review.getRange("A2:J2").format = {
  fill: COLORS.navy,
  font: { name: FONT, size: 16, bold: true, color: "#FFFFFF" },
  verticalAlignment: "center",
  rowHeight: 32,
};
review.mergeCells("A3:J3");
review.getRange("A3").values = [["R7 严格导入已通过，但五类覆盖缺少“非标准”。本表只修正 1 条存在直接二次开发证据的样本，不影响其余 119 条。请确认建议，或退回并在备注中说明。"]];
review.getRange("A3:J3").format = {
  fill: COLORS.red,
  font: { name: FONT, size: 10, bold: true, color: COLORS.redText },
  wrapText: true,
  verticalAlignment: "center",
  rowHeight: 42,
};

review.getRange("A5:F5").values = [["确认决定", "未确认", "确认人", "", "确认日期", ""]];
review.getRange("A5:F5").format = {
  font: { name: FONT, size: 10, color: COLORS.text },
  verticalAlignment: "center",
  borders: { preset: "all", style: "thin", color: COLORS.border },
  rowHeight: 28,
};
for (const address of ["A5", "C5", "E5"]) {
  review.getRange(address).format.font = { name: FONT, size: 10, bold: true, color: COLORS.blue };
}
review.getRange("B5").format.fill = COLORS.amberStrong;
review.getRange("D5:F5").format.fill = COLORS.amber;
review.getRange("F5").format.numberFormat = "yyyy-mm-dd";
review.getRange("B5").dataValidation = {
  rule: { type: "list", values: ["未确认", "确认本次修正", "退回修正"] },
};

review.getRange("A8:J8").values = [[
  "CaseId",
  "R7当前问题",
  "R7当前分类",
  "建议改写问题",
  "建议分类",
  "直接依据",
  "建议引用Chunk",
  "打开证据",
  "人工备注",
  "确认状态",
]];
header(review.getRange("A8:J8"));
review.getRange("A9:J9").values = [[
  item.case_id,
  item.current_query,
  item.current_classification,
  item.proposed_query,
  item.proposed_classification,
  item.rationale,
  item.chunk_id,
  null,
  "",
  null,
]];
review.getRange("H9").formulas = [[`=HYPERLINK("${item.evidence_link}","打开证据 ►")`]];
review.getRange("J9").formulas = [[`=IF($B$5="确认本次修正","已确认",IF($B$5="退回修正","已退回","待确认"))`]];
body(review.getRange("A9:J9"));
review.getRange("D9:G9").format.fill = COLORS.green;
review.getRange("H9").format = {
  fill: COLORS.paleBlue,
  font: { name: FONT, size: 10, bold: true, color: "#0563C1", underline: "single" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
review.getRange("I9").format.fill = COLORS.amber;
review.getRange("J9").conditionalFormats.addCustom("=J9=\"待确认\"", {
  fill: COLORS.red,
  font: { bold: true, color: COLORS.redText },
});
review.getRange("J9").conditionalFormats.addCustom("=J9=\"已确认\"", {
  fill: COLORS.green,
  font: { bold: true, color: "#375623" },
});
review.getRange("A:A").format.columnWidth = 12;
review.getRange("B:B").format.columnWidth = 52;
review.getRange("C:C").format.columnWidth = 28;
review.getRange("D:D").format.columnWidth = 68;
review.getRange("E:E").format.columnWidth = 30;
review.getRange("F:F").format.columnWidth = 58;
review.getRange("G:G").format.columnWidth = 42;
review.getRange("H:H").format.columnWidth = 16;
review.getRange("I:I").format.columnWidth = 38;
review.getRange("J:J").format.columnWidth = 14;
review.getRange("9:9").format.rowHeight = 132;
review.freezePanes.freezeRows(8);

evidence.mergeCells("A2:F2");
evidence.getRange("A2").values = [["为何建议改为“非标准”"]];
evidence.getRange("A2:F2").format = {
  fill: COLORS.navy,
  font: { name: FONT, size: 15, bold: true, color: "#FFFFFF" },
  rowHeight: 30,
};
evidence.getRange("A5:F5").values = [["CaseId", "来源文件", "位置", "证据摘要", "判定规则", "打开原文"]];
header(evidence.getRange("A5:F5"));
evidence.getRange("A6:F6").values = [[
  item.case_id,
  item.source_name,
  item.location_label,
  item.evidence_excerpt,
  "只有证据明确说明需要定制、二次开发或标准能力不支持时，才能判为非标准。本条证据直接出现二次开发交付物。",
  null,
]];
if (item.original_url) {
  evidence.getRange("F6").formulas = [[`=HYPERLINK("${item.original_url}","打开原文 ►")`]];
}
body(evidence.getRange("A6:F6"));
evidence.getRange("D6:E6").format.fill = COLORS.green;
evidence.getRange("F6").format = {
  fill: COLORS.paleBlue,
  font: { name: FONT, size: 10, bold: true, color: "#0563C1", underline: "single" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
evidence.getRange("A:A").format.columnWidth = 12;
evidence.getRange("B:B").format.columnWidth = 46;
evidence.getRange("C:C").format.columnWidth = 18;
evidence.getRange("D:D").format.columnWidth = 82;
evidence.getRange("E:E").format.columnWidth = 62;
evidence.getRange("F:F").format.columnWidth = 16;
evidence.getRange("6:6").format.rowHeight = 118;
evidence.freezePanes.freezeRows(5);

workbook.recalculate();
await fs.mkdir(outputDir, { recursive: true });
review.getRange("H9").values = [["打开证据 ►"]];
evidence.getRange("F6").values = [[item.original_url ? "打开原文 ►" : "原文未定位"]];
for (const [sheetName, range, fileName] of [
  ["R7.1确认", "A1:J12", "preview-r7-1-confirmation.png"],
  ["证据说明", "A1:F8", "preview-r7-1-evidence.png"],
]) {
  const preview = await workbook.render({ sheetName, range, scale: 1.15, format: "png" });
  await fs.writeFile(path.join(outputDir, fileName), new Uint8Array(await preview.arrayBuffer()));
}
review.getRange("H9").formulas = [[`=HYPERLINK("${item.evidence_link}","打开证据 ►")`]];
if (item.original_url) {
  evidence.getRange("F6").formulas = [[`=HYPERLINK("${item.original_url}","打开原文 ►")`]];
}
workbook.recalculate();

const outputPath = path.join(outputDir, "POC-03-R7非标准例外确认-R7.1.xlsx");
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

const saved = await SpreadsheetFile.importXlsx(await FileBlob.load(outputPath));
const validation = [];
for (const [sheetName, range] of [["R7.1确认", "A1:J12"], ["证据说明", "A1:F8"]]) {
  const inspected = await saved.inspect({
    kind: "table",
    range: `${sheetName}!${range}`,
    include: "values,formulas",
    tableMaxRows: 12,
    tableMaxCols: 10,
    maxChars: 18000,
  });
  validation.push(inspected.ndjson);
}
const errors = await saved.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 100 },
  maxChars: 8000,
});
validation.push(errors.ndjson);
await fs.writeFile(path.join(outputDir, "artifact-tool-validation-r7-1.ndjson"), validation.join("\n"), "utf8");
console.log(JSON.stringify({ status: "AWAITING_HUMAN_CONFIRMATION", outputPath, caseId: item.case_id, previewCount: 2 }));
