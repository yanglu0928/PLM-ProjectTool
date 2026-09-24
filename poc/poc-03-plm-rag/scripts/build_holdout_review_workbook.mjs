import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const packagePath = process.argv[2];
const outputDir = process.argv[3];
if (!packagePath || !outputDir) {
  throw new Error("Usage: node build_holdout_review_workbook.mjs <review-package.json> <output-dir>");
}

const reviewPackage = JSON.parse(await fs.readFile(packagePath, "utf8"));
const cases = reviewPackage.cases || [];
if (cases.length !== 50) {
  throw new Error(`Holdout review requires exactly 50 cases, got ${cases.length}`);
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
    fill: COLORS.amber,
    font: { name: FONT, size: 10, bold: true, color: "#7F6000" },
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
const review = workbook.worksheets.add("确认清单");
const guide = workbook.worksheets.add("分类说明");
const audit = workbook.worksheets.add("技术底稿");
for (const [sheet, color] of [
  [review, COLORS.navy],
  [guide, "#ED7D31"],
  [audit, "#A5A5A5"],
]) {
  sheet.showGridLines = false;
  sheet.tabColor = color;
}

styleTitle(
  review,
  "POC-03 独立留出集 AI 建议确认",
  "最省事：在 B5 选择“确认全部AI建议”，填写审核人和日期即可。只有需要修改或退回的条目才维护黄色列。点击“打开证据”可查看原文位置和打开源文件。",
  "L",
);
review.getRange("A5:H7").values = [
  ["批量处理", "待确认", "审核人", "", "审核日期", "", "评审范围", 50],
  ["已确认", null, "待处理", null, "已退回", null, "原文定位", reviewPackage.unresolved_original_count === 0 ? "50/50" : "存在缺失"],
  ["证据原则", "实际调研记录为主要事实证据", "表单用途", "仅供参考", "当前用途", "独立留出集人工确认", "质量门槛", "保持90%/98%"],
];
review.getRange("B6").formulas = [["=COUNTIF(L10:L59,\"已确认\")"]];
review.getRange("D6").formulas = [["=COUNTIF(L10:L59,\"待确认\")+COUNTIF(L10:L59,\"待补充\")+COUNTIF(L10:L59,\"填写审核信息\")"]];
review.getRange("F6").formulas = [["=COUNTIF(L10:L59,\"已退回\")"]];
review.getRange("A5:H7").format = {
  font: { name: FONT, size: 10, color: COLORS.text },
  verticalAlignment: "center",
  wrapText: true,
  borders: { preset: "outside", style: "thin", color: COLORS.border },
};
for (const address of ["A5", "C5", "E5", "G5", "A6", "C6", "E6", "G6", "A7", "C7", "E7", "G7"]) {
  review.getRange(address).format.font = { name: FONT, size: 10, bold: true, color: COLORS.blue };
}
review.getRange("B5").format.fill = COLORS.amberStrong;
review.getRange("D5:F5").format.fill = COLORS.amber;
review.getRange("F5").format.numberFormat = "yyyy-mm-dd";
review.getRange("B5").dataValidation = {
  rule: { type: "list", values: ["待确认", "确认全部AI建议"] },
};

const headers = [
  "复核编号",
  "资料类别",
  "AI建议问题",
  "AI建议分类",
  "AI分类理由",
  "证据位置",
  "打开证据",
  "单条处理",
  "人工最终问题",
  "人工最终分类",
  "人工说明",
  "生效状态",
];
review.getRange("A9:L9").values = [headers];
styleHeader(review.getRange("A9:L9"));
review.getRange("A10:L59").values = cases.map((item) => [
  item.task_id,
  item.source_type_display,
  item.suggested_question,
  item.suggested_classification_display,
  item.classification_reason,
  item.location_label,
  null,
  "",
  "",
  "",
  "",
  null,
]);
const evidenceFormulas = cases.map((item) => [
  `=HYPERLINK("${item.evidence_link}","打开证据")`,
]);
review.getRange("G10:G59").formulas = evidenceFormulas;
for (let row = 10; row <= 59; row += 1) {
  review.getRange(`L${row}`).formulas = [[
    `=IF(OR($D$5="",$F$5=""),"填写审核信息",IF(H${row}="退回","已退回",IF(H${row}="修改后确认",IF(AND(I${row}<>"",J${row}<>"",K${row}<>""),"已确认","待补充"),IF(OR($B$5="确认全部AI建议",H${row}="确认AI建议"),"已确认","待确认"))))`,
  ]];
}
review.getRange("H10:H59").dataValidation = {
  rule: { type: "list", values: ["确认AI建议", "修改后确认", "退回"] },
};
review.getRange("J10:J59").dataValidation = {
  rule: { type: "list", values: CLASSIFICATION_OPTIONS },
};
bodyStyle(review.getRange("A10:L59"));
review.getRange("H10:K59").format.fill = COLORS.amber;
review.getRange("G10:G59").format = {
  fill: COLORS.paleBlue,
  font: { name: FONT, size: 10, bold: true, color: "#0563C1", underline: "single" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
review.getRange("L10:L59").conditionalFormats.addCustom('=L10="待确认"', {
  fill: COLORS.red,
  font: { bold: true, color: COLORS.redText },
});
review.getRange("L10:L59").conditionalFormats.addCustom('=L10="待补充"', {
  fill: COLORS.red,
  font: { bold: true, color: COLORS.redText },
});
review.getRange("L10:L59").conditionalFormats.addCustom('=L10="填写审核信息"', {
  fill: COLORS.amber,
  font: { bold: true, color: "#7F6000" },
});
review.getRange("L10:L59").conditionalFormats.addCustom('=L10="已确认"', {
  fill: COLORS.green,
  font: { bold: true, color: COLORS.greenText },
});
review.getRange("L10:L59").conditionalFormats.addCustom('=L10="已退回"', {
  fill: COLORS.red,
  font: { bold: true, color: COLORS.redText },
});
review.getRange("A:A").format.columnWidth = 12;
review.getRange("B:B").format.columnWidth = 18;
review.getRange("C:C").format.columnWidth = 58;
review.getRange("D:D").format.columnWidth = 34;
review.getRange("E:E").format.columnWidth = 46;
review.getRange("F:F").format.columnWidth = 34;
review.getRange("G:G").format.columnWidth = 14;
review.getRange("H:H").format.columnWidth = 16;
review.getRange("I:I").format.columnWidth = 58;
review.getRange("J:J").format.columnWidth = 34;
review.getRange("K:K").format.columnWidth = 38;
review.getRange("L:L").format.columnWidth = 14;
review.getRange("10:59").format.rowHeight = 92;
review.freezePanes.freezeRows(9);
review.freezePanes.freezeColumns(2);

styleTitle(
  guide,
  "五类业务结论说明",
  "请按证据能够证明的事实选择分类。只有存在明确的定制、二次开发、特殊接口或特殊交付证据时，才能判定为“非标准”。",
  "E",
);
guide.getRange("A6:E6").values = [["分类", "代码", "适用条件", "不应这样使用", "人工确认重点"]];
styleHeader(guide.getRange("A6:E6"));
guide.getRange("A7:E11").values = [
  ["标准满足", "STANDARD_SATISFIED", "证据可直接证明现有标准能力完整满足目标。", "仅有相关功能词或客户需求描述。", "前置条件、范围、限制和是否仍需定制。"],
  ["部分满足", "PARTIALLY_SATISFIED", "证据只覆盖部分范围，或满足依赖明确条件。", "证据完全充分或完全没有可靠匹配。", "缺口、条件和边界是否明确。"],
  ["非标准", "NON_STANDARD", "证据明确说明需定制、二次开发、特殊接口或特殊交付。", "只因为需求复杂，或没有找到标准能力证据。", "必须存在直接的非标依据。"],
  ["资料不足", "INSUFFICIENT_INFORMATION", "候选与事项相关，但不足以判断满足程度或实施方式。", "完全无关的候选。", "还缺少哪些事实才能得出结论。"],
  ["无可靠匹配", "NO_RELIABLE_MATCH", "候选未直接回答判定目标。", "只是证据位置较深或表达不完整。", "确认确无可靠证据，而不是漏检。"],
];
bodyStyle(guide.getRange("A7:E11"));
guide.getRange("A7:A11").format.font = { name: FONT, size: 10, bold: true, color: COLORS.blue };
guide.getRange("A:A").format.columnWidth = 16;
guide.getRange("B:B").format.columnWidth = 34;
guide.getRange("C:E").format.columnWidth = 48;
guide.getRange("7:11").format.rowHeight = 62;
guide.getRange("A13:E14").values = [
  ["调研证据", "实际访谈和交流记录", "作为主要事实证据", "业务表单", "仅作问题清单与字段参考"],
  ["验收门槛", "分类≥90%", "引用≥98%", "当前状态", "待人工确认，不能提前计分"],
];
guide.getRange("A13:E14").format = {
  fill: COLORS.amber,
  font: { name: FONT, size: 10, bold: true, color: "#7F6000" },
  wrapText: true,
  borders: { preset: "all", style: "thin", color: COLORS.border },
};
guide.freezePanes.freezeRows(6);

styleTitle(
  audit,
  "独立留出集技术底稿",
  "用于严格导入和来源锁定追溯。客户正文、模型逐条响应和人工身份信息不会提交到 Git。",
  "L",
);
audit.getRange("A6:L6").values = [[
  "候选编号", "复核编号", "资料类别", "证据角色", "文档编号", "ChunkId", "正文Hash", "来源定位", "摘录本地修复", "关键词本地修复", "来源文件", "锁指纹",
]];
styleHeader(audit.getRange("A6:L6"));
audit.getRange("A7:L56").values = cases.map((item) => [
  item.candidate_id,
  item.task_id,
  item.source_type,
  item.evidence_role,
  item.document_id,
  item.chunk_id,
  item.text_sha256,
  item.source_locators.join("；"),
  item.evidence_quote_repaired ? "是" : "否",
  item.answer_terms_repaired ? "是" : "否",
  item.source_name,
  reviewPackage.lock_fingerprint,
]);
bodyStyle(audit.getRange("A7:L56"));
audit.getRange("A:B").format.columnWidth = 15;
audit.getRange("C:D").format.columnWidth = 28;
audit.getRange("E:G").format.columnWidth = 44;
audit.getRange("H:H").format.columnWidth = 60;
audit.getRange("I:J").format.columnWidth = 16;
audit.getRange("K:K").format.columnWidth = 48;
audit.getRange("L:L").format.columnWidth = 68;
audit.getRange("7:56").format.rowHeight = 46;
audit.freezePanes.freezeRows(6);
audit.freezePanes.freezeColumns(2);

workbook.recalculate();
await fs.mkdir(outputDir, { recursive: true });

review.getRange("G10:G59").values = cases.map(() => ["打开证据"]);
for (const [sheetName, range, fileName] of [
  ["确认清单", "A1:L22", "preview-confirmation.png"],
  ["分类说明", "A1:E14", "preview-guide.png"],
  ["技术底稿", "A1:L20", "preview-audit.png"],
]) {
  const preview = await workbook.render({ sheetName, range, scale: 1.1, format: "png" });
  await fs.writeFile(path.join(outputDir, fileName), new Uint8Array(await preview.arrayBuffer()));
}
review.getRange("G10:G59").formulas = evidenceFormulas;
workbook.recalculate();

const outputPath = path.join(outputDir, "POC-03-独立留出集AI建议确认-R1.xlsx");
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

const saved = await SpreadsheetFile.importXlsx(await FileBlob.load(outputPath));
const validation = [];
for (const [sheetName, range, rows, cols] of [
  ["确认清单", "A1:L18", 18, 12],
  ["分类说明", "A1:E14", 14, 5],
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

const interactionSheet = saved.worksheets.getItem("确认清单");
interactionSheet.getRange("B5").values = [["确认全部AI建议"]];
interactionSheet.getRange("D5").values = [["回归测试"]];
interactionSheet.getRange("F5").values = [[new Date("2026-09-20T00:00:00+08:00")]];
saved.recalculate();
validation.push((await saved.inspect({
  kind: "table",
  range: "确认清单!A5:L10",
  include: "values,formulas",
  tableMaxRows: 6,
  tableMaxCols: 12,
  maxChars: 12000,
})).ndjson);
interactionSheet.getRange("H10").values = [["修改后确认"]];
interactionSheet.getRange("I10").values = [["人工修订问题？"]];
interactionSheet.getRange("J10").values = [[CLASSIFICATION_OPTIONS[0]]];
interactionSheet.getRange("K10").values = [[""]];
saved.recalculate();
validation.push((await saved.inspect({
  kind: "table",
  range: "确认清单!H10:L10",
  include: "values,formulas",
  tableMaxRows: 1,
  tableMaxCols: 5,
  maxChars: 4000,
})).ndjson);
interactionSheet.getRange("K10").values = [["人工修改说明"]];
saved.recalculate();
validation.push((await saved.inspect({
  kind: "table",
  range: "确认清单!H10:L10",
  include: "values,formulas",
  tableMaxRows: 1,
  tableMaxCols: 5,
  maxChars: 4000,
})).ndjson);
await fs.writeFile(path.join(outputDir, "artifact-tool-validation.ndjson"), validation.join("\n"), "utf8");

console.log(JSON.stringify({
  status: "AWAITING_HUMAN_CONFIRMATION",
  outputPath,
  scopeCount: cases.length,
  previewCount: 3,
}));
