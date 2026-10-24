import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";


const [packagePath, outputDir] = process.argv.slice(2);
if (!packagePath || !outputDir) {
  throw new Error("Usage: node build_delegated_requirement_review_workbook.mjs <package.json> <output-dir>");
}

const payload = JSON.parse(await fs.readFile(packagePath, "utf8"));
const projects = payload.projects;
const decisions = payload.decisions;
const requirements = payload.requirements;

const FONT = "Arial";
const COLORS = {
  navy: "#17365D",
  blue: "#1F4E78",
  paleBlue: "#DDEBF7",
  border: "#D9E2F3",
  text: "#1F2937",
  muted: "#667085",
  green: "#E2F0D9",
  greenText: "#375623",
  amber: "#FFF2CC",
  amberText: "#7F6000",
  red: "#FCE4D6",
  redText: "#9C0006",
  gray: "#F2F2F2",
};

const workbook = Workbook.create();
const overview = workbook.worksheets.add("评审总览");
const decisionSheet = workbook.worksheets.add("代决策结果");
const requirementSheet = workbook.worksheets.add("需求评审稿");
const guide = workbook.worksheets.add("使用边界");
overview.tabColor = COLORS.navy;
decisionSheet.tabColor = "#ED7D31";
requirementSheet.tabColor = "#70AD47";
guide.tabColor = "#A5A5A5";
for (const sheet of [overview, decisionSheet, requirementSheet, guide]) {
  sheet.showGridLines = false;
}

function title(sheet, heading, context, lastColumn) {
  sheet.getRange(`A2:${lastColumn}2`).format = {
    font: { name: FONT, size: 14, bold: true, color: COLORS.navy },
    verticalAlignment: "center",
  };
  sheet.getRange("A2").values = [[heading]];
  sheet.getRange(`A3:${lastColumn}3`).format = {
    font: { name: FONT, size: 10, italic: true, color: COLORS.muted },
    verticalAlignment: "top",
    wrapText: false,
    borders: { bottom: { style: "thin", color: COLORS.border } },
  };
  sheet.getRange("A3").values = [[context]];
  sheet.getRange("2:2").format.rowHeight = 24;
  sheet.getRange("3:3").format.rowHeight = 20;
}

function header(range) {
  range.format = {
    fill: COLORS.blue,
    font: { name: FONT, size: 10, bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
    borders: {
      insideVertical: { style: "thin", color: "#FFFFFF" },
      bottom: { style: "medium", color: COLORS.navy },
    },
  };
  range.format.rowHeight = 34;
}

function body(range) {
  range.format = {
    font: { name: FONT, size: 10, color: COLORS.text },
    verticalAlignment: "top",
    wrapText: true,
    borders: { bottom: { style: "thin", color: COLORS.border } },
  };
}

function formulaEscape(value) {
  return String(value || "").replaceAll('"', '""');
}

const p0Count = requirements.filter((row) => row.review_priority === "P0").length;
const p1Count = requirements.filter((row) => row.review_priority === "P1").length;
const highRiskCount = requirements.filter((row) => row.risk === "高").length;

title(
  overview,
  "第一批项目需求评审",
  "AI 已按用户授权代为处理普通确认和资料缺口。40 条候选已进入内部需求评审稿；它们不是正式 Requirement，也不代表客户确认。",
  "J",
);
overview.getRange("A5:J5").values = [[
  "项目", projects.length,
  "需求评审稿", requirements.length,
  "代决策事项", decisions.length,
  "P0", p0Count,
  "正式需求", 0,
]];
overview.getRange("A5:J5").format = {
  fill: COLORS.gray,
  font: { name: FONT, size: 10, color: COLORS.text },
  verticalAlignment: "center",
  borders: { preset: "outside", style: "thin", color: COLORS.border },
};
for (const cell of ["A5", "C5", "E5", "G5", "I5"]) {
  overview.getRange(cell).format.font = { name: FONT, size: 10, bold: true, color: COLORS.blue };
}
for (const cell of ["B5", "D5", "F5", "H5", "J5"]) {
  overview.getRange(cell).format.font = { name: FONT, size: 12, bold: true, color: COLORS.navy };
  overview.getRange(cell).format.horizontalAlignment = "center";
}

overview.getRange("A8:I8").values = [[
  "项目", "需求数", "P0", "P1", "代决策事项", "高风险", "内部状态", "下一动作", "正式化限制",
]];
header(overview.getRange("A8:I8"));
const projectStart = 9;
const projectEnd = projectStart + projects.length - 1;
overview.getRange(`A${projectStart}:I${projectEnd}`).values = projects.map((row) => [
  row.project_name,
  row.requirement_count,
  row.p0_count,
  row.p1_count,
  row.working_decision_count,
  row.high_risk_count,
  "需求评审稿已生成",
  row.next_action,
  "需通过正式 Gate 后才能转成正式 Requirement",
]);
body(overview.getRange(`A${projectStart}:I${projectEnd}`));
overview.getRange(`G${projectStart}:G${projectEnd}`).format = {
  fill: COLORS.green,
  font: { name: FONT, size: 10, bold: true, color: COLORS.greenText },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
overview.getRange("A:A").format.columnWidth = 34;
overview.getRange("B:F").format.columnWidth = 12;
overview.getRange("G:G").format.columnWidth = 24;
overview.getRange("H:I").format.columnWidth = 54;
overview.getRange(`${projectStart}:${projectEnd}`).format.rowHeight = 72;

overview.getRange("A17:I21").values = [
  ["决策原则", "适用范围", "", "", "", "", "", "", ""],
  ["证据优先", "实际调研与合同/技术约束优先，方案和风险材料保留假设标识。", "", "", "", "", "", "", ""],
  ["保守默认", "未知范围不承诺自动化、实时性或性能；优先选择可配置、可回滚实现。", "", "", "", "", "", "", ""],
  ["最小影响", "一个缺口不阻塞其他候选分析，但受影响需求不得据此升级为正式事实。", "", "", "", "", "", "", ""],
  ["正式化边界", "客户数据外发、正式 Gate、锁定基线、安全和 License 仍需专项确认。", "", "", "", "", "", "", ""],
];
for (const row of [17, 18, 19, 20, 21]) {
  overview.mergeCells(`B${row}:I${row}`);
}
overview.getRange("A17:I21").format = {
  font: { name: FONT, size: 10, color: COLORS.text },
  verticalAlignment: "center",
  wrapText: true,
  borders: { bottom: { style: "thin", color: COLORS.border } },
};
overview.getRange("A17:I17").format = {
  fill: COLORS.gray,
  font: { name: FONT, size: 10, bold: true, color: COLORS.blue },
};
overview.getRange("17:21").format.rowHeight = 34;
overview.freezePanes.freezeRows(8);
overview.freezePanes.freezeColumns(1);

title(
  decisionSheet,
  "代决策结果",
  "10 条原前置假设均采用保守工作基线。决策只解除内部分析阻塞；正式需求、合同解释和客户确认仍受对应 Gate 约束。",
  "N",
);
decisionSheet.getRange("A6:N6").values = [[
  "决策编号", "项目", "原待决策事项", "资料依据", "决策类型", "推荐决定", "纳入范围", "明确排除", "验收依据", "风险", "状态", "授权来源", "打开证据", "正式化限制",
]];
header(decisionSheet.getRange("A6:N6"));
const decisionStart = 7;
const decisionEnd = decisionStart + decisions.length - 1;
decisionSheet.getRange(`A${decisionStart}:N${decisionEnd}`).values = decisions.map((row) => [
  row.decision_id,
  row.project_name,
  row.issue,
  row.source_basis,
  row.profile,
  row.recommended_decision,
  row.included_scope,
  row.explicit_exclusion,
  row.acceptance_basis,
  row.risk,
  row.status,
  row.authority,
  null,
  row.formalization,
]);
const decisionLinks = decisions.map((row) => [
  `=HYPERLINK("${formulaEscape(row.evidence_link)}","打开证据")`,
]);
decisionSheet.getRange(`M${decisionStart}:M${decisionEnd}`).formulas = decisionLinks;
body(decisionSheet.getRange(`A${decisionStart}:N${decisionEnd}`));
decisionSheet.getRange(`M${decisionStart}:M${decisionEnd}`).format = {
  fill: COLORS.paleBlue,
  font: { name: FONT, size: 10, bold: true, color: "#0563C1", underline: "single" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
decisionSheet.getRange(`J${decisionStart}:J${decisionEnd}`).conditionalFormats.addCustom(
  `=J${decisionStart}="高"`,
  { fill: COLORS.red, font: { bold: true, color: COLORS.redText } },
);
decisionSheet.getRange(`K${decisionStart}:K${decisionEnd}`).format = {
  fill: COLORS.amber,
  font: { name: FONT, size: 10, bold: true, color: COLORS.amberText },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
decisionSheet.tables.add(`A6:N${decisionEnd}`, true, "DelegatedDecisionsTable").style = "TableStyleMedium2";
decisionSheet.getRange("A:A").format.columnWidth = 18;
decisionSheet.getRange("B:B").format.columnWidth = 34;
decisionSheet.getRange("C:D").format.columnWidth = 54;
decisionSheet.getRange("E:E").format.columnWidth = 32;
decisionSheet.getRange("F:I").format.columnWidth = 64;
decisionSheet.getRange("J:J").format.columnWidth = 10;
decisionSheet.getRange("K:L").format.columnWidth = 30;
decisionSheet.getRange("M:M").format.columnWidth = 15;
decisionSheet.getRange("N:N").format.columnWidth = 34;
decisionSheet.getRange(`${decisionStart}:${decisionEnd}`).format.rowHeight = 110;
decisionSheet.freezePanes.freezeRows(6);
decisionSheet.freezePanes.freezeColumns(2);

title(
  requirementSheet,
  "需求评审稿",
  "40 条候选已完成 AI 代决策收敛并进入内部评审稿。P0 优先完成边界、接口和验收设计；所有条目仍标记为非正式需求。",
  "R",
);
requirementSheet.getRange("A6:R6").values = [[
  "候选编号", "项目", "优先级", "类型", "业务域", "名称", "需求描述", "验收标准草案", "实施说明", "能力匹配", "AI 处置", "决策依据", "关联决策", "风险", "打开证据", "评审状态", "正式状态", "草案版本",
]];
header(requirementSheet.getRange("A6:R6"));
const requirementStart = 7;
const requirementEnd = requirementStart + requirements.length - 1;
requirementSheet.getRange(`A${requirementStart}:R${requirementEnd}`).values = requirements.map((row) => [
  row.candidate_id,
  row.project_name,
  row.review_priority,
  row.kind,
  row.domain,
  row.title,
  row.statement,
  row.acceptance_draft,
  row.implementation_note,
  row.capability_match,
  row.ai_disposition,
  row.decision_basis,
  row.resolution_id,
  row.risk,
  null,
  row.review_status,
  row.formal_status,
  row.draft_version,
]);
const requirementLinks = requirements.map((row) => [
  `=HYPERLINK("${formulaEscape(row.evidence_link)}","打开证据")`,
]);
requirementSheet.getRange(`O${requirementStart}:O${requirementEnd}`).formulas = requirementLinks;
body(requirementSheet.getRange(`A${requirementStart}:R${requirementEnd}`));
requirementSheet.getRange(`O${requirementStart}:O${requirementEnd}`).format = {
  fill: COLORS.paleBlue,
  font: { name: FONT, size: 10, bold: true, color: "#0563C1", underline: "single" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
requirementSheet.getRange(`C${requirementStart}:C${requirementEnd}`).conditionalFormats.addCustom(
  `=C${requirementStart}="P0"`,
  { fill: COLORS.red, font: { bold: true, color: COLORS.redText } },
);
requirementSheet.getRange(`N${requirementStart}:N${requirementEnd}`).conditionalFormats.addCustom(
  `=N${requirementStart}="高"`,
  { fill: COLORS.red, font: { bold: true, color: COLORS.redText } },
);
requirementSheet.getRange(`Q${requirementStart}:Q${requirementEnd}`).format = {
  fill: COLORS.gray,
  font: { name: FONT, size: 10, bold: true, color: COLORS.muted },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
requirementSheet.tables.add(`A6:R${requirementEnd}`, true, "RequirementReviewTable").style = "TableStyleMedium4";
requirementSheet.getRange("A:A").format.columnWidth = 17;
requirementSheet.getRange("B:B").format.columnWidth = 34;
requirementSheet.getRange("C:C").format.columnWidth = 10;
requirementSheet.getRange("D:E").format.columnWidth = 20;
requirementSheet.getRange("F:F").format.columnWidth = 48;
requirementSheet.getRange("G:I").format.columnWidth = 62;
requirementSheet.getRange("J:J").format.columnWidth = 28;
requirementSheet.getRange("K:L").format.columnWidth = 56;
requirementSheet.getRange("M:M").format.columnWidth = 20;
requirementSheet.getRange("N:N").format.columnWidth = 10;
requirementSheet.getRange("O:O").format.columnWidth = 15;
requirementSheet.getRange("P:Q").format.columnWidth = 28;
requirementSheet.getRange("R:R").format.columnWidth = 14;
requirementSheet.getRange(`${requirementStart}:${requirementEnd}`).format.rowHeight = 96;
requirementSheet.freezePanes.freezeRows(6);
requirementSheet.freezePanes.freezeColumns(2);

title(
  guide,
  "使用边界",
  "本包替用户完成普通项目分析决策，不要求逐条维护。使用时保留证据链接、工作基线和正式化限制。",
  "F",
);
guide.getRange("A6:F6").values = [["对象", "当前状态", "已经完成", "下一环节", "不能自动完成", "变更方式"]];
header(guide.getRange("A6:F6"));
guide.getRange("A7:F10").values = [
  ["代决策事项", "ADOPTED_WORKING_BASELINE", "已给出范围、排除项、验收依据和风险", "纳入内部需求评审", "客户确认、合同正式解释", "保留原决策并登记新版本"],
  ["需求候选", "INTERNAL_REVIEW_DRAFT", "40 条均已给出处置和优先级", "标准能力匹配与解决方案草案", "转成正式 Requirement", "通过 Review Engine 和正式 Gate"],
  ["正式 Gate", "未通过", "未改变 Phase 0 状态", "等待对应技术和业务成果完成", "由 AI 使用概括授权自动批准", "按 Gate 汇总后专项确认"],
  ["外部调用", "本轮未调用", "全部处理在本地完成", "无", "将客户资料发送给外部模型", "取得当轮明确数据外发授权"],
];
body(guide.getRange("A7:F10"));
guide.getRange("A7:A10").format.font = { name: FONT, size: 10, bold: true, color: COLORS.blue };
guide.getRange("A:A").format.columnWidth = 22;
guide.getRange("B:B").format.columnWidth = 28;
guide.getRange("C:F").format.columnWidth = 52;
guide.getRange("7:10").format.rowHeight = 68;
guide.getRange("A13:F18").values = [
  ["统计", "数量", "说明", "", "", ""],
  ["项目", projects.length, "第一批项目", "", "", ""],
  ["需求评审稿", requirements.length, "全部保持非正式状态", "", "", ""],
  ["P0 / P1", `${p0Count} / ${p1Count}`, "P0 优先完善边界与验收", "", "", ""],
  ["代决策事项", decisions.length, "全部采用工作基线", "", "", ""],
  ["高风险条目", highRiskCount, "需在解决方案中保留控制措施", "", "", ""],
];
guide.getRange("A13:C18").format = {
  font: { name: FONT, size: 10, color: COLORS.text },
  verticalAlignment: "center",
  wrapText: true,
  borders: { bottom: { style: "thin", color: COLORS.border } },
};
guide.getRange("A13:C13").format = {
  fill: COLORS.gray,
  font: { name: FONT, size: 10, bold: true, color: COLORS.blue },
};
guide.getRange("B14:B18").format.horizontalAlignment = "right";
guide.getRange("14:18").format.rowHeight = 32;

workbook.recalculate();
await fs.mkdir(outputDir, { recursive: true });

const linkRanges = [
  { sheet: decisionSheet, address: `M${decisionStart}:M${decisionEnd}`, formulas: decisionLinks, values: decisions.map(() => ["打开证据"]) },
  { sheet: requirementSheet, address: `O${requirementStart}:O${requirementEnd}`, formulas: requirementLinks, values: requirements.map(() => ["打开证据"]) },
];
for (const linkRange of linkRanges) {
  linkRange.sheet.getRange(linkRange.address).values = linkRange.values;
}

const previews = [
  ["评审总览", "A1:J21", "preview-评审总览.png"],
  ["代决策结果", `A1:N${decisionEnd}`, "preview-代决策结果.png"],
  ["需求评审稿", "A1:R18", "preview-需求评审稿.png"],
  ["使用边界", "A1:F18", "preview-使用边界.png"],
];
for (const [sheetName, range, fileName] of previews) {
  const preview = await workbook.render({ sheetName, range, scale: 1.05, format: "png" });
  await fs.writeFile(path.join(outputDir, fileName), new Uint8Array(await preview.arrayBuffer()));
}
for (const linkRange of linkRanges) {
  linkRange.sheet.getRange(linkRange.address).formulas = linkRange.formulas;
}
workbook.recalculate();

const outputPath = path.join(outputDir, "第一批项目需求评审-R4.xlsx");
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

const saved = await SpreadsheetFile.importXlsx(await FileBlob.load(outputPath));
const validation = [];
for (const [sheetName, range, rows, cols] of [
  ["评审总览", "A1:J21", 21, 10],
  ["代决策结果", `A1:N${decisionEnd}`, decisionEnd, 14],
  ["需求评审稿", "A1:R18", 18, 18],
  ["使用边界", "A1:F18", 18, 6],
]) {
  validation.push((await saved.inspect({
    kind: "table",
    range: `${sheetName}!${range}`,
    include: "values,formulas",
    tableMaxRows: rows,
    tableMaxCols: cols,
    maxChars: 30000,
  })).ndjson);
}
validation.push((await saved.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 300 },
  maxChars: 12000,
})).ndjson);
validation.push((await saved.inspect({
  kind: "formula",
  sheetId: "代决策结果",
  range: `M${decisionStart}:M${decisionEnd}`,
  maxChars: 8000,
  options: { maxResults: decisions.length },
})).ndjson);
validation.push((await saved.inspect({
  kind: "formula",
  sheetId: "需求评审稿",
  range: `O${requirementStart}:O${requirementEnd}`,
  maxChars: 16000,
  options: { maxResults: requirements.length },
})).ndjson);

await fs.writeFile(path.join(outputDir, "artifact-tool-validation.ndjson"), validation.join("\n"), "utf8");
await fs.writeFile(path.join(outputDir, "workbook-result.json"), JSON.stringify({
  status: payload.status,
  output_path: outputPath,
  project_count: projects.length,
  decision_count: decisions.length,
  requirement_count: requirements.length,
  p0_count: p0Count,
  p1_count: p1Count,
  high_risk_count: highRiskCount,
  preview_count: previews.length,
}, null, 2), "utf8");

console.log(JSON.stringify({
  status: payload.status,
  outputPath,
  projectCount: projects.length,
  decisionCount: decisions.length,
  requirementCount: requirements.length,
  p0Count,
  p1Count,
  highRiskCount,
  previewCount: previews.length,
}));
