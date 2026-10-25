import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";


const [packagePath, outputDir] = process.argv.slice(2);
if (!packagePath || !outputDir) {
  throw new Error("Usage: node build_desktop_discovery_workbook.mjs <package.json> <output-dir>");
}

const payload = JSON.parse(await fs.readFile(packagePath, "utf8"));
const projects = payload.projects;
const results = payload.discovery_results;
const requirements = payload.requirements;
const assumptions = payload.assumptions;

const FONT = "Arial";
const COLORS = {
  navy: "#17365D",
  blue: "#1F4E78",
  paleBlue: "#DDEBF7",
  border: "#D9E2F3",
  text: "#1F2937",
  muted: "#667085",
  amber: "#FFF2CC",
  amberText: "#7F6000",
  green: "#E2F0D9",
  greenText: "#375623",
  red: "#FCE4D6",
  redText: "#9C0006",
  gray: "#F2F2F2",
};

const workbook = Workbook.create();
const overview = workbook.worksheets.add("结果总览");
const discovery = workbook.worksheets.add("桌面调研结果");
const requirementSheet = workbook.worksheets.add("需求候选");
const assumptionSheet = workbook.worksheets.add("前置假设");
const guide = workbook.worksheets.add("使用说明");

overview.tabColor = COLORS.navy;
discovery.tabColor = COLORS.blue;
requirementSheet.tabColor = "#70AD47";
assumptionSheet.tabColor = "#ED7D31";
guide.tabColor = "#A5A5A5";
for (const sheet of [overview, discovery, requirementSheet, assumptionSheet, guide]) {
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
  range.format.rowHeight = 32;
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

const readyCount = requirements.filter((item) => item.status === "DRAFT_READY").length;
const assumedCount = requirements.filter((item) => item.status === "DRAFT_WITH_ASSUMPTION").length;
const blockedCount = requirements.filter((item) => item.status === "BLOCKED_BY_DECISION").length;

title(
  overview,
  "第一批项目桌面调研与需求候选",
  "因无法安排新的客户访谈，本轮仅依据现有资料生成桌面调研结果并进入需求候选准备。资料推断和工作假设不得描述为客户已确认事实，也不进入正式需求冻结。",
  "J",
);
overview.getRange("A5:J5").values = [[
  "项目", projects.length, "调研结果", results.length, "需求候选", requirements.length, "可评审草案", readyCount + assumedCount, "前置决策", blockedCount,
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

overview.getRange("A8:J8").values = [[
  "项目", "资料成熟度", "调研结果", "需求候选", "可评审", "带假设", "前置决策", "阶段状态", "项目结论摘要", "下一动作",
]];
header(overview.getRange("A8:J8"));
const projectStart = 9;
const projectEnd = projectStart + projects.length - 1;
overview.getRange(`A${projectStart}:J${projectEnd}`).values = projects.map((project) => [
  project.project_name,
  project.source_maturity,
  project.discovery_result_count,
  project.requirement_count,
  project.draft_ready_count,
  project.assumption_count,
  project.blocked_count,
  "需求候选已生成",
  project.summary,
  project.next_action,
]);
body(overview.getRange(`A${projectStart}:J${projectEnd}`));
overview.getRange(`H${projectStart}:H${projectEnd}`).format = {
  fill: COLORS.green,
  font: { name: FONT, size: 10, bold: true, color: COLORS.greenText },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
overview.getRange("A:A").format.columnWidth = 34;
overview.getRange("B:B").format.columnWidth = 24;
overview.getRange("C:G").format.columnWidth = 12;
overview.getRange("H:H").format.columnWidth = 20;
overview.getRange("I:I").format.columnWidth = 76;
overview.getRange("J:J").format.columnWidth = 50;
overview.getRange(`${projectStart}:${projectEnd}`).format.rowHeight = 88;
overview.freezePanes.freezeRows(8);
overview.freezePanes.freezeColumns(1);

title(
  discovery,
  "桌面调研结果",
  "每条结果都标明证据层级和限制。结果可直接进入需求候选分析，但不是本轮新增客户确认。点击“打开证据”可回到 R1 分析依据和原始本地文件。",
  "M",
);
discovery.getRange("A6:M6").values = [[
  "结果编号", "项目", "优先级", "主题", "桌面调研结论", "证据层级", "置信度", "使用限制", "预期产出", "关联分析", "打开证据", "下一环节", "状态",
]];
header(discovery.getRange("A6:M6"));
const resultStart = 7;
const resultEnd = resultStart + results.length - 1;
discovery.getRange(`A${resultStart}:M${resultEnd}`).values = results.map((item) => [
  item.result_id,
  item.project_name,
  item.priority,
  item.topic,
  item.result,
  item.evidence_level,
  item.confidence,
  item.limitation,
  item.expected_output,
  item.related_item_ids.join("、"),
  null,
  item.next_stage,
  item.review_status,
]);
const resultLinks = results.map((item) => [
  `=HYPERLINK("${formulaEscape(item.evidence_link)}","打开证据")`,
]);
discovery.getRange(`K${resultStart}:K${resultEnd}`).formulas = resultLinks;
body(discovery.getRange(`A${resultStart}:M${resultEnd}`));
discovery.getRange(`K${resultStart}:K${resultEnd}`).format = {
  fill: COLORS.paleBlue,
  font: { name: FONT, size: 10, bold: true, color: "#0563C1", underline: "single" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
discovery.getRange(`C${resultStart}:C${resultEnd}`).conditionalFormats.addCustom(
  `=C${resultStart}="P0"`,
  { fill: COLORS.red, font: { bold: true, color: COLORS.redText } },
);
discovery.tables.add(`A6:M${resultEnd}`, true, "DesktopDiscoveryTable").style = "TableStyleMedium2";
discovery.getRange("A:A").format.columnWidth = 15;
discovery.getRange("B:B").format.columnWidth = 34;
discovery.getRange("C:C").format.columnWidth = 10;
discovery.getRange("D:D").format.columnWidth = 26;
discovery.getRange("E:E").format.columnWidth = 72;
discovery.getRange("F:F").format.columnWidth = 24;
discovery.getRange("G:G").format.columnWidth = 11;
discovery.getRange("H:H").format.columnWidth = 60;
discovery.getRange("I:I").format.columnWidth = 34;
discovery.getRange("J:K").format.columnWidth = 15;
discovery.getRange("L:L").format.columnWidth = 26;
discovery.getRange("M:M").format.columnWidth = 18;
discovery.getRange(`${resultStart}:${resultEnd}`).format.rowHeight = 82;
discovery.freezePanes.freezeRows(6);
discovery.freezePanes.freezeColumns(2);

title(
  requirementSheet,
  "需求候选",
  "40 条候选已经从 R1 分析和桌面调研结果转入下一环节。黄色列仅用于后续需求评审；当前状态不是正式 Requirement，也未进入需求冻结。",
  "Q",
);
requirementSheet.getRange("A6:Q6").values = [[
  "候选编号", "项目", "类型", "业务域", "名称", "候选需求描述", "验收标准草案", "实施说明", "能力匹配", "置信度", "来源追溯", "打开证据", "系统状态", "评审结论", "修订说明", "评审人", "评审日期",
]];
header(requirementSheet.getRange("A6:Q6"));
const requirementStart = 7;
const requirementEnd = requirementStart + requirements.length - 1;
requirementSheet.getRange(`A${requirementStart}:Q${requirementEnd}`).values = requirements.map((item) => [
  item.candidate_id,
  item.project_name,
  item.kind,
  item.domain,
  item.title,
  item.statement,
  item.acceptance_draft,
  item.implementation_note,
  item.capability_match,
  item.confidence,
  item.trace_source,
  null,
  item.status,
  item.review_decision,
  item.review_notes,
  "",
  null,
]);
const requirementLinks = requirements.map((item) => [
  `=HYPERLINK("${formulaEscape(item.evidence_link)}","打开证据")`,
]);
requirementSheet.getRange(`L${requirementStart}:L${requirementEnd}`).formulas = requirementLinks;
body(requirementSheet.getRange(`A${requirementStart}:Q${requirementEnd}`));
requirementSheet.getRange(`L${requirementStart}:L${requirementEnd}`).format = {
  fill: COLORS.paleBlue,
  font: { name: FONT, size: 10, bold: true, color: "#0563C1", underline: "single" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
requirementSheet.getRange(`N${requirementStart}:Q${requirementEnd}`).format.fill = COLORS.amber;
requirementSheet.getRange(`N${requirementStart}:N${requirementEnd}`).dataValidation = {
  rule: { type: "list", values: ["待需求评审", "接受为候选", "修改后接受", "退回", "暂缓"] },
};
requirementSheet.getRange(`Q${requirementStart}:Q${requirementEnd}`).format.numberFormat = "yyyy-mm-dd";
requirementSheet.getRange(`M${requirementStart}:M${requirementEnd}`).conditionalFormats.addCustom(
  `=M${requirementStart}="BLOCKED_BY_DECISION"`,
  { fill: COLORS.red, font: { bold: true, color: COLORS.redText } },
);
requirementSheet.getRange(`M${requirementStart}:M${requirementEnd}`).conditionalFormats.addCustom(
  `=M${requirementStart}="DRAFT_WITH_ASSUMPTION"`,
  { fill: COLORS.amber, font: { bold: true, color: COLORS.amberText } },
);
requirementSheet.tables.add(`A6:Q${requirementEnd}`, true, "RequirementCandidatesTable").style = "TableStyleMedium4";
requirementSheet.getRange(`N${requirementStart}:Q${requirementEnd}`).format.fill = COLORS.amber;
requirementSheet.getRange("A:A").format.columnWidth = 16;
requirementSheet.getRange("B:B").format.columnWidth = 34;
requirementSheet.getRange("C:C").format.columnWidth = 20;
requirementSheet.getRange("D:D").format.columnWidth = 20;
requirementSheet.getRange("E:E").format.columnWidth = 48;
requirementSheet.getRange("F:F").format.columnWidth = 58;
requirementSheet.getRange("G:G").format.columnWidth = 68;
requirementSheet.getRange("H:H").format.columnWidth = 54;
requirementSheet.getRange("I:I").format.columnWidth = 28;
requirementSheet.getRange("J:K").format.columnWidth = 14;
requirementSheet.getRange("L:L").format.columnWidth = 15;
requirementSheet.getRange("M:N").format.columnWidth = 24;
requirementSheet.getRange("O:O").format.columnWidth = 48;
requirementSheet.getRange("P:Q").format.columnWidth = 16;
requirementSheet.getRange(`${requirementStart}:${requirementEnd}`).format.rowHeight = 88;
requirementSheet.freezePanes.freezeRows(6);
requirementSheet.freezePanes.freezeColumns(2);

title(
  assumptionSheet,
  "前置假设与待决策",
  "以下 10 项不能因无法安排访谈而自动关闭。系统已给出可继续分析的工作假设，但相关需求、接口、范围或验收规则在决策前不得冻结。",
  "I",
);
assumptionSheet.getRange("A6:I6").values = [[
  "假设编号", "项目", "待决策事项", "资料依据", "当前工作假设", "影响", "打开证据", "状态", "下一动作",
]];
header(assumptionSheet.getRange("A6:I6"));
const assumptionStart = 7;
const assumptionEnd = assumptionStart + assumptions.length - 1;
assumptionSheet.getRange(`A${assumptionStart}:I${assumptionEnd}`).values = assumptions.map((item) => [
  item.assumption_id,
  item.project_name,
  item.issue,
  item.basis,
  item.working_assumption,
  item.impact,
  null,
  item.status,
  "在需求评审时指定责任人并形成唯一书面结论。",
]);
const assumptionLinks = assumptions.map((item) => [
  `=HYPERLINK("${formulaEscape(item.evidence_link)}","打开证据")`,
]);
assumptionSheet.getRange(`G${assumptionStart}:G${assumptionEnd}`).formulas = assumptionLinks;
body(assumptionSheet.getRange(`A${assumptionStart}:I${assumptionEnd}`));
assumptionSheet.getRange(`G${assumptionStart}:G${assumptionEnd}`).format = {
  fill: COLORS.paleBlue,
  font: { name: FONT, size: 10, bold: true, color: "#0563C1", underline: "single" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
assumptionSheet.getRange(`H${assumptionStart}:H${assumptionEnd}`).format = {
  fill: COLORS.red,
  font: { name: FONT, size: 10, bold: true, color: COLORS.redText },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
assumptionSheet.tables.add(`A6:I${assumptionEnd}`, true, "WorkingAssumptionsTable").style = "TableStyleMedium2";
assumptionSheet.getRange("A:A").format.columnWidth = 16;
assumptionSheet.getRange("B:B").format.columnWidth = 34;
assumptionSheet.getRange("C:C").format.columnWidth = 48;
assumptionSheet.getRange("D:F").format.columnWidth = 60;
assumptionSheet.getRange("G:G").format.columnWidth = 15;
assumptionSheet.getRange("H:H").format.columnWidth = 28;
assumptionSheet.getRange("I:I").format.columnWidth = 48;
assumptionSheet.getRange(`${assumptionStart}:${assumptionEnd}`).format.rowHeight = 88;
assumptionSheet.freezePanes.freezeRows(6);
assumptionSheet.freezePanes.freezeColumns(2);

title(
  guide,
  "使用说明",
  "本成果用于在无法安排第一批访谈时继续推进分析。先看结果总览，再查看桌面调研结果和需求候选；前置假设必须保持可见，不得伪装为已确认结论。",
  "F",
);
guide.getRange("A6:F6").values = [["对象", "本轮含义", "可以做什么", "不能做什么", "证据要求", "下一状态"]];
header(guide.getRange("A6:F6"));
guide.getRange("A7:F10").values = [
  ["桌面调研结果", "依据现有资料形成的项目结论", "进入需求候选分析、识别标准/非标/差异", "声称本轮已完成客户访谈或客户确认", "每条保留 R1 分析项和本地原文入口", "桌面调研草案"],
  ["需求候选", "从已确认 R1 分析基线转出的下一环节输入", "拆分、合并、能力匹配和验收设计", "作为正式 Requirement 或进入需求冻结", "必须有 Trace 来源和证据链接", "待需求评审"],
  ["前置假设", "为不中断分析而采用的临时工作假设", "用于识别影响、准备备选方案", "自动关闭待确认项或固化接口/范围/验收规则", "明确限制、影响和待决策事项", "OPEN"],
  ["正式需求", "经项目负责人评审确认的版本化 Requirement", "进入能力匹配、方案和原型", "本工作簿不能直接生成正式状态", "需完整 Trace、验收标准和人工确认", "本轮未进入"],
];
body(guide.getRange("A7:F10"));
guide.getRange("A7:A10").format.font = { name: FONT, size: 10, bold: true, color: COLORS.blue };
guide.getRange("A:A").format.columnWidth = 22;
guide.getRange("B:F").format.columnWidth = 48;
guide.getRange("7:10").format.rowHeight = 72;
guide.getRange("A13:F17").values = [
  ["状态", "解释", "后续处理", "", "", ""],
  ["DRAFT_READY", "已有实际调研或合同/技术约束，可进入需求候选评审", "继续完善验收标准和边界", "", "", ""],
  ["DRAFT_WITH_ASSUMPTION", "主要来自方案或风险材料", "保持假设标识，需求评审时重点复核", "", "", ""],
  ["BLOCKED_BY_DECISION", "关键规则仍未确定", "可并行分析，但不得冻结受影响需求", "", "", ""],
  ["外部调用", "本轮为完全本地处理", "不包含独立留出集复验授权", "", "", ""],
];
guide.getRange("A13:C17").format = {
  font: { name: FONT, size: 10, color: COLORS.text },
  verticalAlignment: "top",
  wrapText: true,
  borders: { bottom: { style: "thin", color: COLORS.border } },
};
guide.getRange("A13:C13").format = {
  fill: COLORS.gray,
  font: { name: FONT, size: 10, bold: true, color: COLORS.blue },
  borders: { bottom: { style: "thin", color: COLORS.border } },
};
guide.getRange("14:17").format.rowHeight = 38;

workbook.recalculate();
await fs.mkdir(outputDir, { recursive: true });

const linkRanges = [
  { sheet: discovery, address: `K${resultStart}:K${resultEnd}`, formulas: resultLinks, values: results.map(() => ["打开证据"]) },
  { sheet: requirementSheet, address: `L${requirementStart}:L${requirementEnd}`, formulas: requirementLinks, values: requirements.map(() => ["打开证据"]) },
  { sheet: assumptionSheet, address: `G${assumptionStart}:G${assumptionEnd}`, formulas: assumptionLinks, values: assumptions.map(() => ["打开证据"]) },
];
for (const linkRange of linkRanges) {
  linkRange.sheet.getRange(linkRange.address).values = linkRange.values;
}

const previews = [
  ["结果总览", `A1:J${projectEnd}`, "preview-结果总览.png"],
  ["桌面调研结果", "A1:M18", "preview-桌面调研结果.png"],
  ["需求候选", "A1:Q18", "preview-需求候选.png"],
  ["前置假设", `A1:I${assumptionEnd}`, "preview-前置假设.png"],
  ["使用说明", "A1:F17", "preview-使用说明.png"],
];
for (const [sheetName, range, fileName] of previews) {
  const preview = await workbook.render({ sheetName, range, scale: 1.05, format: "png" });
  await fs.writeFile(path.join(outputDir, fileName), new Uint8Array(await preview.arrayBuffer()));
}
for (const linkRange of linkRanges) {
  linkRange.sheet.getRange(linkRange.address).formulas = linkRange.formulas;
}
workbook.recalculate();

const outputPath = path.join(outputDir, "第一批项目桌面调研与需求候选-R3.xlsx");
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

const saved = await SpreadsheetFile.importXlsx(await FileBlob.load(outputPath));
const validation = [];
for (const [sheetName, range, rows, cols] of [
  ["结果总览", `A1:J${projectEnd}`, projectEnd, 10],
  ["桌面调研结果", "A1:M18", 18, 13],
  ["需求候选", "A1:Q18", 18, 17],
  ["前置假设", `A1:I${assumptionEnd}`, assumptionEnd, 9],
  ["使用说明", "A1:F17", 17, 6],
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

const reviewSheet = saved.worksheets.getItem("需求候选");
reviewSheet.getRange("N7:Q7").values = [["修改后接受", "回归测试：收敛一期边界", "回归测试", new Date("2026-09-21T00:00:00+08:00")]];
saved.recalculate();
validation.push((await saved.inspect({
  kind: "table",
  range: "需求候选!L6:Q7",
  include: "values,formulas",
  tableMaxRows: 2,
  tableMaxCols: 6,
  maxChars: 5000,
})).ndjson);

await fs.writeFile(path.join(outputDir, "artifact-tool-validation.ndjson"), validation.join("\n"), "utf8");
await fs.writeFile(path.join(outputDir, "workbook-result.json"), JSON.stringify({
  status: payload.status,
  output_path: outputPath,
  project_count: projects.length,
  discovery_result_count: results.length,
  requirement_count: requirements.length,
  ready_count: readyCount,
  assumed_count: assumedCount,
  blocked_count: blockedCount,
  preview_count: previews.length,
}, null, 2), "utf8");

console.log(JSON.stringify({
  status: payload.status,
  outputPath,
  projectCount: projects.length,
  discoveryResultCount: results.length,
  requirementCount: requirements.length,
  readyCount,
  assumedCount,
  blockedCount,
  previewCount: previews.length,
}));
