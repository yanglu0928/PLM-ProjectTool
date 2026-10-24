import fs from "node:fs/promises";
import path from "node:path";
import { Workbook, SpreadsheetFile, FileBlob } from "@oai/artifact-tool";

const packagePath = process.argv[2];
const outputDir = process.argv[3];
if (!packagePath || !outputDir) {
  throw new Error("Usage: node build_r6_citation_review.mjs <r6-package.json> <output-dir>");
}

const reviewPackage = JSON.parse(await fs.readFile(packagePath, "utf8"));
const cases = reviewPackage.cases || [];
if (cases.length !== 6) {
  throw new Error(`R6 requires exactly six review cases, got ${cases.length}`);
}

const FONT = "Microsoft YaHei";
const COLORS = {
  navy: "#17365D",
  blue: "#1F4E78",
  paleBlue: "#D9EAF7",
  amber: "#FFF2CC",
  amberStrong: "#FFD966",
  green: "#E2F0D9",
  greenText: "#375623",
  red: "#FCE4D6",
  redText: "#9C0006",
  gray: "#F2F2F2",
  border: "#B4C6E7",
  text: "#1F2937",
};

function styleTitle(sheet, title, subtitle, endColumn) {
  sheet.getRange(`A2:${endColumn}2`).format.borders = { bottom: { style: "thin", color: COLORS.navy } };
  sheet.getRange("A2").values = [[title]];
  sheet.getRange("A2").format.font = { name: FONT, size: 15, bold: true, color: COLORS.navy };
  sheet.mergeCells(`A3:${endColumn}3`);
  sheet.getRange("A3").values = [[subtitle]];
  sheet.getRange(`A3:${endColumn}3`).format = {
    fill: COLORS.red,
    font: { name: FONT, size: 10, bold: true, color: COLORS.redText },
    wrapText: true,
    verticalAlignment: "center",
    rowHeight: 38,
  };
}

function styleHeader(range) {
  range.format = {
    fill: COLORS.navy,
    font: { name: FONT, size: 10, bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "all", style: "thin", color: "#FFFFFF" },
    rowHeight: 40,
  };
}

function bodyStyle(range) {
  range.format.font = { name: FONT, size: 10, color: COLORS.text };
  range.format.verticalAlignment = "top";
  range.format.wrapText = true;
  range.format.borders = {
    insideHorizontal: { style: "thin", color: "#D9E2F3" },
    bottom: { style: "thin", color: COLORS.border },
  };
}

const workbook = Workbook.create();
const review = workbook.worksheets.add("R6确认");
const citations = workbook.worksheets.add("引用建议");
const audit = workbook.worksheets.add("技术底稿");
for (const [sheet, color] of [[review, COLORS.navy], [citations, "#70AD47"], [audit, "#A5A5A5"]]) {
  sheet.showGridLines = false;
  sheet.tabColor = color;
}

styleTitle(
  review,
  "POC-03 Golden R6 · 六项低区分度样本确认",
  "最省事的确认方式：在 B5 选择“确认全部AI建议”，填写确认人和日期即可。只在某条建议不适用时，才维护黄色列；点击“打开证据”可查看原核定 Chunk 与 Top-5 对照。",
  "M",
);
review.getRange("A5:F7").values = [
  ["批量确认", "未确认", "确认人", "", "确认日期", new Date("2026-09-18T00:00:00+08:00")],
  ["需复核项", 6, "已确认", null, "待确认", null],
  ["保持不变", reviewPackage.preserved_case_count, "分类标签变更", 0, "引用默认", "R5原核定Chunk"],
];
review.getRange("D6").formulas = [["=COUNTIF(M10:M15,\"已确认\")"]];
review.getRange("F6").formulas = [["=COUNTIF(M10:M15,\"待确认\")"]];
review.getRange("A5:F7").format = {
  font: { name: FONT, size: 10, color: COLORS.text },
  verticalAlignment: "center",
  borders: { preset: "outside", style: "thin", color: COLORS.border },
};
for (const address of ["A5", "C5", "E5", "A6", "C6", "E6", "A7", "C7", "E7"]) {
  review.getRange(address).format.font = { name: FONT, size: 10, bold: true, color: COLORS.blue };
}
review.getRange("B5").format.fill = COLORS.amberStrong;
review.getRange("D5:F5").format.fill = COLORS.amber;
review.getRange("F5").format.numberFormat = "yyyy-mm-dd";
review.getRange("B5").dataValidation = { rule: { type: "list", values: ["未确认", "确认全部AI建议"] } };

const headers = [
  "复核编号", "CaseId", "资料类别", "当前分类", "当前问题", "问题原因", "AI建议修订问题",
  "AI建议引用Chunk", "打开证据", "单条决定", "人工修订问题", "人工引用Chunk", "生效状态",
];
review.getRange("A9:M9").values = [headers];
styleHeader(review.getRange("A9:M9"));
review.getRange("A10:M15").values = cases.map((item) => [
  item.task_id,
  item.case_id,
  item.source_type,
  item.classification,
  item.original_query,
  item.issue_reason,
  item.suggested_query,
  item.suggested_chunk_ids.join("；"),
  null,
  "",
  "",
  "",
  null,
]);
const evidenceFormulas = cases.map((item) => [`=HYPERLINK("${item.evidence_link}","打开证据 ►")`]);
review.getRange("I10:I15").formulas = evidenceFormulas;
for (let row = 10; row <= 15; row += 1) {
  review.getRange(`M${row}`).formulas = [[
    `=IF(J${row}="退回","已退回",IF(OR($B$5="确认全部AI建议",J${row}="确认AI建议",J${row}="修改后确认"),"已确认","待确认"))`,
  ]];
}
review.getRange("J10:J15").dataValidation = {
  rule: { type: "list", values: ["确认AI建议", "修改后确认", "退回"] },
};
bodyStyle(review.getRange("A10:M15"));
review.getRange("J10:L15").format.fill = COLORS.amber;
review.getRange("I10:I15").format = {
  fill: COLORS.paleBlue,
  font: { name: FONT, size: 10, bold: true, color: "#0563C1", underline: "single" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
review.getRange("M10:M15").conditionalFormats.addCustom("=M10=\"待确认\"", { fill: COLORS.red, font: { bold: true, color: COLORS.redText } });
review.getRange("M10:M15").conditionalFormats.addCustom("=M10=\"已确认\"", { fill: COLORS.green, font: { bold: true, color: COLORS.greenText } });
review.getRange("A:A").format.columnWidth = 11;
review.getRange("B:B").format.columnWidth = 12;
review.getRange("C:D").format.columnWidth = 23;
review.getRange("E:E").format.columnWidth = 42;
review.getRange("F:F").format.columnWidth = 38;
review.getRange("G:G").format.columnWidth = 55;
review.getRange("H:H").format.columnWidth = 37;
review.getRange("I:I").format.columnWidth = 16;
review.getRange("J:J").format.columnWidth = 17;
review.getRange("K:K").format.columnWidth = 52;
review.getRange("L:L").format.columnWidth = 38;
review.getRange("M:M").format.columnWidth = 12;
review.getRange("10:15").format.rowHeight = 88;
review.freezePanes.freezeRows(9);
review.freezePanes.freezeColumns(2);

styleTitle(
  citations,
  "R6 引用建议与 Top-5 对照",
  "绿色“原核定引用”是 AI 默认建议；其余行仅用于判断是否存在语义等价引用，不会自动写入 Golden Dataset。",
  "H",
);
const citationHeaders = ["CaseId", "类型", "当前排名", "ChunkId", "文档编号", "位置", "内容摘要", "打开证据"];
citations.getRange("A6:H6").values = [citationHeaders];
styleHeader(citations.getRange("A6:H6"));
const citationRows = cases.flatMap((item) => item.candidate_chunks.map((chunk) => [
  item.case_id,
  chunk.is_expected ? "原核定引用" : "Top-5对照",
  chunk.rank,
  chunk.chunk_id,
  chunk.document_id,
  chunk.location_label,
  chunk.snippet,
  null,
]));
const citationStart = 7;
const citationEnd = citationStart + citationRows.length - 1;
citations.getRangeByIndexes(citationStart - 1, 0, citationRows.length, 8).values = citationRows;
const citationLinks = cases.flatMap((item) => item.candidate_chunks.map((chunk) => [
  `=HYPERLINK("evidence-navigator.html#${chunk.chunk_id}","定位 ►")`,
]));
citations.getRange(`H${citationStart}:H${citationEnd}`).formulas = citationLinks;
bodyStyle(citations.getRange(`A${citationStart}:H${citationEnd}`));
for (let index = 0; index < citationRows.length; index += 1) {
  if (citationRows[index][1] === "原核定引用") {
    citations.getRange(`A${citationStart + index}:H${citationStart + index}`).format.fill = COLORS.green;
  }
}
citations.getRange(`H${citationStart}:H${citationEnd}`).format.font = { name: FONT, color: "#0563C1", underline: "single" };
citations.getRange("A:A").format.columnWidth = 12;
citations.getRange("B:B").format.columnWidth = 16;
citations.getRange("C:C").format.columnWidth = 10;
citations.getRange("D:E").format.columnWidth = 42;
citations.getRange("F:F").format.columnWidth = 30;
citations.getRange("G:G").format.columnWidth = 78;
citations.getRange("H:H").format.columnWidth = 12;
citations.getRange(`${citationStart}:${citationEnd}`).format.rowHeight = 58;
citations.freezePanes.freezeRows(6);
citations.freezePanes.freezeColumns(2);

styleTitle(
  audit,
  "R6 技术底稿",
  "用于严格导入、范围锁定和回归追溯。R6 只允许修改以下 6 个 Case 的问题和引用；其他 114 条及全部 R5 分类保持不变。",
  "J",
);
const auditHeaders = ["CaseId", "复核编号", "R5分类", "原核定Chunk", "原核定排名", "允许引用数", "Top-5", "来源文件", "R6范围", "R5数据集"];
audit.getRange("A6:J6").values = [auditHeaders];
styleHeader(audit.getRange("A6:J6"));
audit.getRange("A7:J12").values = cases.map((item) => [
  item.case_id,
  item.task_id,
  item.classification,
  item.suggested_chunk_ids.join("；"),
  item.expected_rank,
  item.allowed_chunk_ids.length,
  item.candidate_chunks.filter((chunk) => !chunk.is_expected).map((chunk) => chunk.chunk_id).join("；"),
  item.source_name,
  "仅问题与引用",
  reviewPackage.source_dataset_id,
]);
bodyStyle(audit.getRange("A7:J12"));
audit.getRange("A:B").format.columnWidth = 13;
audit.getRange("C:C").format.columnWidth = 26;
audit.getRange("D:D").format.columnWidth = 42;
audit.getRange("E:F").format.columnWidth = 13;
audit.getRange("G:G").format.columnWidth = 80;
audit.getRange("H:H").format.columnWidth = 55;
audit.getRange("I:I").format.columnWidth = 18;
audit.getRange("J:J").format.columnWidth = 34;
audit.getRange("7:12").format.rowHeight = 45;
audit.freezePanes.freezeRows(6);
audit.freezePanes.freezeColumns(2);

workbook.recalculate();
await fs.mkdir(outputDir, { recursive: true });

// Artifact Tool does not calculate HYPERLINK. Render human-friendly labels, then restore links for Excel.
review.getRange("I10:I15").values = cases.map(() => ["打开证据 ►"]);
citations.getRange(`H${citationStart}:H${citationEnd}`).values = citationRows.map(() => ["定位 ►"]);
for (const [sheetName, range, fileName] of [
  ["R6确认", "A1:M15", "preview-r6-confirmation.png"],
  ["引用建议", `A1:H${Math.min(citationEnd, 20)}`, "preview-r6-citations.png"],
  ["技术底稿", "A1:J12", "preview-r6-audit.png"],
]) {
  const preview = await workbook.render({ sheetName, range, scale: 1.25, format: "png" });
  await fs.writeFile(path.join(outputDir, fileName), new Uint8Array(await preview.arrayBuffer()));
}
review.getRange("I10:I15").formulas = evidenceFormulas;
citations.getRange(`H${citationStart}:H${citationEnd}`).formulas = citationLinks;
workbook.recalculate();

const outputPath = path.join(outputDir, "POC-03-Golden问题与引用确认-R6.xlsx");
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

const saved = await SpreadsheetFile.importXlsx(await FileBlob.load(outputPath));
const validation = [];
for (const [sheetName, range] of [["R6确认", "A1:M15"], ["引用建议", "A1:H14"], ["技术底稿", "A1:J12"]]) {
  const inspected = await saved.inspect({
    kind: "table",
    range: `${sheetName}!${range}`,
    include: "values,formulas",
    tableMaxRows: 20,
    tableMaxCols: 13,
    maxChars: 18000,
  });
  validation.push(inspected.ndjson);
}
const errors = await saved.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 100 },
  maxChars: 8000,
});
validation.push(errors.ndjson);
await fs.writeFile(path.join(outputDir, "artifact-tool-validation-r6.ndjson"), validation.join("\n"), "utf8");
console.log(JSON.stringify({ status: "AWAITING_HUMAN_CONFIRMATION", outputPath, scopeCount: cases.length, citationRowCount: citationRows.length, previewCount: 3 }));
