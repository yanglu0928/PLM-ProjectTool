import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const packagePath = process.argv[2];
const outputDir = process.argv[3];
if (!packagePath || !outputDir) {
  throw new Error("Usage: node build_r7_semantic_review.mjs <r7-package.json> <output-dir>");
}

const reviewPackage = JSON.parse(await fs.readFile(packagePath, "utf8"));
const cases = reviewPackage.cases || [];
if (cases.length !== 120) {
  throw new Error(`R7 requires exactly 120 review cases, got ${cases.length}`);
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

const CLASSIFICATION_OPTIONS = [
  "标准满足（STANDARD_SATISFIED）",
  "部分满足（PARTIALLY_SATISFIED）",
  "非标准（NON_STANDARD）",
  "资料不足（INSUFFICIENT_INFORMATION）",
  "无可靠匹配（NO_RELIABLE_MATCH）",
];

function styleTitle(sheet, title, subtitle, endColumn) {
  sheet.getRange(`A2:${endColumn}2`).format.borders = {
    bottom: { style: "thin", color: COLORS.navy },
  };
  sheet.getRange("A2").values = [[title]];
  sheet.getRange("A2").format.font = {
    name: FONT,
    size: 15,
    bold: true,
    color: COLORS.navy,
  };
  sheet.mergeCells(`A3:${endColumn}3`);
  sheet.getRange("A3").values = [[subtitle]];
  sheet.getRange(`A3:${endColumn}3`).format = {
    fill: COLORS.red,
    font: { name: FONT, size: 10, bold: true, color: COLORS.redText },
    wrapText: true,
    verticalAlignment: "center",
    rowHeight: 42,
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
    rowHeight: 42,
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
const review = workbook.worksheets.add("R7确认");
const guide = workbook.worksheets.add("分类说明");
const citations = workbook.worksheets.add("引用候选");
const audit = workbook.worksheets.add("技术底稿");
for (const [sheet, color] of [
  [review, COLORS.navy],
  [guide, "#ED7D31"],
  [citations, "#70AD47"],
  [audit, "#A5A5A5"],
]) {
  sheet.showGridLines = false;
  sheet.tabColor = color;
}

styleTitle(
  review,
  "POC-03 Golden R7 · 语义、分类与引用重新评审",
  "最省事：在 B5 选择“确认全部AI建议”，再填写确认人和确认日期。只在某条不适用时维护黄色列。点击“打开证据”可直接定位原文。R7 是 AI 辅助校准集，同一批 120 条不能用于关闭质量 Gate，后续仍须建立独立留出集。",
  "Q",
);
review.getRange("A5:H7").values = [
  ["批量确认", "未确认", "确认人", "", "确认日期", "", "评审范围", 120],
  ["AI建议改分类", reviewPackage.label_change_suggestion_count, "AI建议改引用", reviewPackage.citation_change_suggestion_count, "已确认", null, "待确认", null],
  ["原文定位", reviewPackage.unresolved_original_count === 0 ? "120/120" : "存在缺失", "导出用途", "校准集", "独立留出集", "必须", "验收门槛", "保持90%/98%"],
];
review.getRange("F6").formulas = [["=COUNTIF(Q10:Q129,\"已确认\")"]];
review.getRange("H6").formulas = [["=COUNTIF(Q10:Q129,\"待确认\")"]];
review.getRange("A5:H7").format = {
  font: { name: FONT, size: 10, color: COLORS.text },
  verticalAlignment: "center",
  borders: { preset: "outside", style: "thin", color: COLORS.border },
};
for (const address of ["A5", "C5", "E5", "G5", "A6", "C6", "E6", "G6", "A7", "C7", "E7", "G7"]) {
  review.getRange(address).format.font = { name: FONT, size: 10, bold: true, color: COLORS.blue };
}
review.getRange("B5").format.fill = COLORS.amberStrong;
review.getRange("D5:F5").format.fill = COLORS.amber;
review.getRange("F5").format.numberFormat = "yyyy-mm-dd";
review.getRange("B5").dataValidation = {
  rule: { type: "list", values: ["未确认", "确认全部AI建议"] },
};

const headers = [
  "复核编号",
  "CaseId",
  "资料类别",
  "R6当前分类",
  "Prompt v2分类",
  "问题诊断",
  "AI建议判定目标",
  "AI建议分类",
  "AI分类理由",
  "AI建议引用Chunk",
  "打开证据",
  "单条决定",
  "人工判定目标",
  "人工最终分类",
  "人工引用Chunk",
  "人工说明",
  "生效状态",
];
review.getRange("A9:Q9").values = [headers];
styleHeader(review.getRange("A9:Q9"));
review.getRange("A10:Q129").values = cases.map((item) => [
  item.task_id,
  item.case_id,
  item.source_type,
  item.current_classification_display || item.current_classification,
  item.prompt_v2_classification_display || item.prompt_v2_classification,
  item.issue_reason,
  item.suggested_target,
  item.suggested_classification_display || item.suggested_classification,
  item.classification_rationale,
  item.suggested_chunk_ids.join("；"),
  null,
  "",
  "",
  "",
  "",
  "",
  null,
]);
const evidenceFormulas = cases.map((item) => [
  `=HYPERLINK("${item.evidence_link}","打开证据 ►")`,
]);
review.getRange("K10:K129").formulas = evidenceFormulas;
for (let row = 10; row <= 129; row += 1) {
  review.getRange(`Q${row}`).formulas = [[
    `=IF(L${row}="退回","已退回",IF(OR($B$5="确认全部AI建议",L${row}="确认AI建议",L${row}="修改后确认"),"已确认","待确认"))`,
  ]];
}
review.getRange("L10:L129").dataValidation = {
  rule: { type: "list", values: ["确认AI建议", "修改后确认", "退回"] },
};
review.getRange("N10:N129").dataValidation = {
  rule: { type: "list", values: CLASSIFICATION_OPTIONS },
};
bodyStyle(review.getRange("A10:Q129"));
review.getRange("L10:P129").format.fill = COLORS.amber;
review.getRange("K10:K129").format = {
  fill: COLORS.paleBlue,
  font: { name: FONT, size: 10, bold: true, color: "#0563C1", underline: "single" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
review.getRange("Q10:Q129").conditionalFormats.addCustom("=Q10=\"待确认\"", {
  fill: COLORS.red,
  font: { bold: true, color: COLORS.redText },
});
review.getRange("Q10:Q129").conditionalFormats.addCustom("=Q10=\"已确认\"", {
  fill: COLORS.green,
  font: { bold: true, color: COLORS.greenText },
});
review.getRange("A:A").format.columnWidth = 12;
review.getRange("B:B").format.columnWidth = 12;
review.getRange("C:C").format.columnWidth = 23;
review.getRange("D:E").format.columnWidth = 34;
review.getRange("F:F").format.columnWidth = 44;
review.getRange("G:G").format.columnWidth = 68;
review.getRange("H:H").format.columnWidth = 34;
review.getRange("I:I").format.columnWidth = 52;
review.getRange("J:J").format.columnWidth = 40;
review.getRange("K:K").format.columnWidth = 16;
review.getRange("L:L").format.columnWidth = 17;
review.getRange("M:M").format.columnWidth = 66;
review.getRange("N:N").format.columnWidth = 34;
review.getRange("O:O").format.columnWidth = 40;
review.getRange("P:P").format.columnWidth = 38;
review.getRange("Q:Q").format.columnWidth = 12;
review.getRange("10:129").format.rowHeight = 104;
review.freezePanes.freezeRows(9);
review.freezePanes.freezeColumns(2);

styleTitle(
  guide,
  "R7 五类业务结论说明",
  "请按证据能够证明的事实选择分类，不按模型偏好选择。尤其注意：只有明确存在定制/二次开发证据时才能判定“非标准”。",
  "E",
);
guide.getRange("A6:E6").values = [["分类", "代码", "适用条件", "不应这样使用", "人工确认重点"]];
styleHeader(guide.getRange("A6:E6"));
guide.getRange("A7:E11").values = [
  ["标准满足", "STANDARD_SATISFIED", "证据可直接证明现有标准能力完整满足目标。", "仅有相关功能词或需求描述。", "前置条件、范围、限制、是否仍需定制。"],
  ["部分满足", "PARTIALLY_SATISFIED", "证据只覆盖部分范围，或满足依赖明确条件。", "证据完全充分或完全没有可靠匹配。", "缺口、条件和边界是否明确。"],
  ["非标准", "NON_STANDARD", "证据明确说明需定制、二次开发或标准能力不支持。", "只因为需求复杂，或没有找到标准能力证据。", "必须存在直接的非标依据。"],
  ["资料不足", "INSUFFICIENT_INFORMATION", "候选与事项相关，但不足以判断满足程度或实施方式。", "完全无关的候选。", "还缺少哪些事实才能得出结论。"],
  ["无可靠匹配", "NO_RELIABLE_MATCH", "所有候选均未直接回答判定目标。", "只是目标引用排名较低。", "确认确无可接受证据，而非漏检。"],
];
bodyStyle(guide.getRange("A7:E11"));
guide.getRange("A7:A11").format.font = { name: FONT, size: 10, bold: true, color: COLORS.blue };
guide.getRange("A:A").format.columnWidth = 16;
guide.getRange("B:B").format.columnWidth = 34;
guide.getRange("C:E").format.columnWidth = 48;
guide.getRange("7:11").format.rowHeight = 62;
guide.getRange("A13:E14").values = [
  ["使用限制", "R7 为 AI 辅助校准集", "同一 120 条不得重新作为独立验收集", "下一步", "另建独立留出集"],
  ["门槛", "分类≥90%", "引用≥98%", "状态", "保持不变"],
];
guide.getRange("A13:E14").format = {
  fill: COLORS.amber,
  font: { name: FONT, size: 10, bold: true, color: COLORS.redText },
  wrapText: true,
  borders: { preset: "all", style: "thin", color: COLORS.border },
};
guide.freezePanes.freezeRows(6);

styleTitle(
  citations,
  "R7 可接受引用候选与原文入口",
  "绿色行是 AI 建议引用，蓝色标识是 R6 原引用。人工修改引用时只能从本表展示的 Chunk 中选择；点击“打开原文”可定位到源文件。",
  "J",
);
const citationHeaders = [
  "CaseId",
  "候选类型",
  "R5排名",
  "ChunkId",
  "文档编号",
  "位置",
  "来源文件",
  "内容摘要",
  "打开证据卡",
  "打开原文",
];
citations.getRange("A6:J6").values = [citationHeaders];
styleHeader(citations.getRange("A6:J6"));
const citationRows = cases.flatMap((item) => item.candidate_chunks.map((chunk) => {
  const types = [];
  if (chunk.is_ai_suggested) types.push("AI建议");
  if (chunk.is_current_expected) types.push("R6原引用");
  if (chunk.retrieval_rank) types.push(`R5 Top-${chunk.retrieval_rank}`);
  return [
    item.case_id,
    types.join(" / ") || "候选",
    chunk.retrieval_rank || "",
    chunk.chunk_id,
    chunk.document_id,
    chunk.location_label,
    chunk.source_name,
    chunk.snippet,
    null,
    null,
  ];
}));
const citationStart = 7;
const citationEnd = citationStart + citationRows.length - 1;
citations.getRangeByIndexes(citationStart - 1, 0, citationRows.length, 10).values = citationRows;
const cardLinks = cases.flatMap((item) => item.candidate_chunks.map((chunk) => [
  `=HYPERLINK("evidence-navigator.html#${chunk.chunk_id}","证据卡 ►")`,
]));
const originalLinks = cases.flatMap((item) => item.candidate_chunks.map((chunk) => [
  chunk.original_url ? `=HYPERLINK("${chunk.original_url}","原文 ►")` : "原文未定位",
]));
citations.getRange(`I${citationStart}:I${citationEnd}`).formulas = cardLinks;
for (let index = 0; index < originalLinks.length; index += 1) {
  const row = citationStart + index;
  const value = originalLinks[index][0];
  if (value.startsWith("=")) citations.getRange(`J${row}`).formulas = [[value]];
  else citations.getRange(`J${row}`).values = [[value]];
}
bodyStyle(citations.getRange(`A${citationStart}:J${citationEnd}`));
for (let index = 0; index < citationRows.length; index += 1) {
  const row = citationStart + index;
  const type = String(citationRows[index][1]);
  if (type.includes("AI建议")) citations.getRange(`A${row}:J${row}`).format.fill = COLORS.green;
  else if (type.includes("R6原引用")) citations.getRange(`A${row}:J${row}`).format.fill = COLORS.paleBlue;
}
citations.getRange(`I${citationStart}:J${citationEnd}`).format.font = {
  name: FONT,
  size: 10,
  color: "#0563C1",
  underline: "single",
};
citations.getRange("A:A").format.columnWidth = 12;
citations.getRange("B:B").format.columnWidth = 24;
citations.getRange("C:C").format.columnWidth = 10;
citations.getRange("D:E").format.columnWidth = 42;
citations.getRange("F:F").format.columnWidth = 32;
citations.getRange("G:G").format.columnWidth = 48;
citations.getRange("H:H").format.columnWidth = 78;
citations.getRange("I:J").format.columnWidth = 14;
citations.getRange(`${citationStart}:${citationEnd}`).format.rowHeight = 68;
citations.freezePanes.freezeRows(6);
citations.freezePanes.freezeColumns(2);

styleTitle(
  audit,
  "R7 技术底稿",
  "用于严格导入、来源锁定和回归追溯。逐条模型响应、客户正文和审核人信息不会提交到 Git。",
  "L",
);
const auditHeaders = [
  "CaseId",
  "复核编号",
  "资料类别",
  "R6分类代码",
  "AI建议分类代码",
  "分类是否变化",
  "R6引用数",
  "AI建议引用数",
  "允许引用数",
  "R5 Top-5",
  "处理用途",
  "来源数据集",
];
audit.getRange("A6:L6").values = [auditHeaders];
styleHeader(audit.getRange("A6:L6"));
audit.getRange("A7:L126").values = cases.map((item) => [
  item.case_id,
  item.task_id,
  item.source_type,
  item.current_classification,
  item.suggested_classification,
  item.current_classification !== item.suggested_classification ? "是" : "否",
  item.current_chunk_ids.length,
  item.suggested_chunk_ids.length,
  item.allowed_chunk_ids.length,
  item.candidate_chunks.filter((chunk) => chunk.retrieval_rank).sort((a, b) => a.retrieval_rank - b.retrieval_rank).map((chunk) => chunk.chunk_id).join("；"),
  "AI辅助校准",
  reviewPackage.source_dataset_id,
]);
bodyStyle(audit.getRange("A7:L126"));
audit.getRange("A:B").format.columnWidth = 14;
audit.getRange("C:C").format.columnWidth = 23;
audit.getRange("D:E").format.columnWidth = 28;
audit.getRange("F:I").format.columnWidth = 14;
audit.getRange("J:J").format.columnWidth = 78;
audit.getRange("K:K").format.columnWidth = 18;
audit.getRange("L:L").format.columnWidth = 38;
audit.getRange("7:126").format.rowHeight = 48;
audit.freezePanes.freezeRows(6);
audit.freezePanes.freezeColumns(2);

workbook.recalculate();
await fs.mkdir(outputDir, { recursive: true });

// Artifact Tool does not calculate HYPERLINK. Render readable labels, then restore links.
review.getRange("K10:K129").values = cases.map(() => ["打开证据 ►"]);
citations.getRange(`I${citationStart}:I${citationEnd}`).values = citationRows.map(() => ["证据卡 ►"]);
citations.getRange(`J${citationStart}:J${citationEnd}`).values = citationRows.map((row, index) => [
  originalLinks[index][0] === "原文未定位" ? "原文未定位" : "原文 ►",
]);
for (const [sheetName, range, fileName] of [
  ["R7确认", "A1:Q24", "preview-r7-confirmation.png"],
  ["分类说明", "A1:E14", "preview-r7-guide.png"],
  ["引用候选", `A1:J${Math.min(citationEnd, 30)}`, "preview-r7-citations.png"],
  ["技术底稿", "A1:L24", "preview-r7-audit.png"],
]) {
  const preview = await workbook.render({ sheetName, range, scale: 1.1, format: "png" });
  await fs.writeFile(path.join(outputDir, fileName), new Uint8Array(await preview.arrayBuffer()));
}
review.getRange("K10:K129").formulas = evidenceFormulas;
citations.getRange(`I${citationStart}:I${citationEnd}`).formulas = cardLinks;
for (let index = 0; index < originalLinks.length; index += 1) {
  const row = citationStart + index;
  const value = originalLinks[index][0];
  if (value.startsWith("=")) citations.getRange(`J${row}`).formulas = [[value]];
  else citations.getRange(`J${row}`).values = [[value]];
}
workbook.recalculate();

const outputPath = path.join(outputDir, "POC-03-Golden语义与引用确认-R7.xlsx");
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

const saved = await SpreadsheetFile.importXlsx(await FileBlob.load(outputPath));
const validation = [];
for (const [sheetName, range, rows, cols] of [
  ["R7确认", "A1:Q18", 18, 17],
  ["分类说明", "A1:E14", 14, 5],
  ["引用候选", `A1:J${Math.min(citationEnd, 18)}`, 18, 10],
  ["技术底稿", "A1:L18", 18, 12],
]) {
  const inspected = await saved.inspect({
    kind: "table",
    range: `${sheetName}!${range}`,
    include: "values,formulas",
    tableMaxRows: rows,
    tableMaxCols: cols,
    maxChars: 24000,
  });
  validation.push(inspected.ndjson);
}
const errors = await saved.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 300 },
  maxChars: 12000,
});
validation.push(errors.ndjson);
await fs.writeFile(
  path.join(outputDir, "artifact-tool-validation-r7.ndjson"),
  validation.join("\n"),
  "utf8",
);
console.log(JSON.stringify({
  status: "AWAITING_HUMAN_CONFIRMATION",
  outputPath,
  scopeCount: cases.length,
  citationRowCount: citationRows.length,
  previewCount: 4,
}));
