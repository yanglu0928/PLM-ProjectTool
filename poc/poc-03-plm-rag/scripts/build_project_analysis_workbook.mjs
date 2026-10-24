import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const packagePath = process.argv[2];
const outputDir = process.argv[3];
if (!packagePath || !outputDir) {
  throw new Error("Usage: node build_project_analysis_workbook.mjs <package.json> <output-dir>");
}

const analysis = JSON.parse(await fs.readFile(packagePath, "utf8"));
const projects = analysis.projects || [];
const items = analysis.items || [];
const outline = analysis.survey_outline || [];
const coverage = analysis.coverage || [];
if (!projects.length || !items.length) {
  throw new Error("Project analysis package is empty");
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

const PROJECT_DECISIONS = ["待确认", "初版可用", "需要调优", "补充资料后再审", "不适用"];
const ITEM_DECISIONS = ["待确认", "接受AI建议", "修改后接受", "不适用", "退回"];

function styleTitle(sheet, title, note, endColumn) {
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
  sheet.getRange("A3").values = [[note]];
  sheet.getRange(`A3:${endColumn}3`).format = {
    fill: COLORS.amber,
    font: { name: FONT, size: 10, bold: true, color: "#7F6000" },
    wrapText: true,
    verticalAlignment: "center",
    rowHeight: 44,
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

function styleBody(range) {
  range.format.font = { name: FONT, size: 10, color: COLORS.text };
  range.format.verticalAlignment = "top";
  range.format.wrapText = true;
  range.format.borders = {
    insideHorizontal: { style: "thin", color: "#D9E2F3" },
    bottom: { style: "thin", color: COLORS.border },
  };
}

function applyDecisionFormatting(sheet, address, firstRow) {
  const range = sheet.getRange(address);
  range.conditionalFormats.addCustom(`=${address.split(":")[0].replace(/\d+$/, firstRow)}="待确认"`, {
    fill: COLORS.amber,
    font: { bold: true, color: "#7F6000" },
  });
  range.conditionalFormats.addCustom(`=${address.split(":")[0].replace(/\d+$/, firstRow)}="接受AI建议"`, {
    fill: COLORS.green,
    font: { bold: true, color: COLORS.greenText },
  });
  range.conditionalFormats.addCustom(`=${address.split(":")[0].replace(/\d+$/, firstRow)}="修改后接受"`, {
    fill: COLORS.green,
    font: { bold: true, color: COLORS.greenText },
  });
  range.conditionalFormats.addCustom(`=${address.split(":")[0].replace(/\d+$/, firstRow)}="退回"`, {
    fill: COLORS.red,
    font: { bold: true, color: COLORS.redText },
  });
}

function sourceSummary(project) {
  const counts = project.source_counts || {};
  const labels = [
    ["调研", counts.ACTUAL_SURVEY || 0],
    ["合同", counts.CONTRACT || 0],
    ["技术协议", counts.TECHNICAL_AGREEMENT || 0],
    ["风险评估", counts.RISK_ASSESSMENT || 0],
    ["方案", counts.SOLUTION || 0],
  ];
  return labels.filter(([, count]) => count > 0).map(([label, count]) => `${label}${count}`).join(" / ") || "无项目资料";
}

function formulaEscape(value) {
  return String(value || "").replaceAll('"', '""');
}

const workbook = Workbook.create();
const overview = workbook.worksheets.add("项目总览");
const standard = workbook.worksheets.add("标准功能");
const nonstandard = workbook.worksheets.add("非标功能");
const gaps = workbook.worksheets.add("差异项");
const pending = workbook.worksheets.add("待确认项");
const survey = workbook.worksheets.add("推荐调研大纲");
const sources = workbook.worksheets.add("资料覆盖");
const guide = workbook.worksheets.add("分类口径");

for (const [sheet, color] of [
  [overview, COLORS.navy],
  [standard, "#548235"],
  [nonstandard, "#C65911"],
  [gaps, COLORS.blue],
  [pending, "#BF9000"],
  [survey, "#7030A0"],
  [sources, "#7F7F7F"],
  [guide, "#ED7D31"],
]) {
  sheet.showGridLines = false;
  sheet.tabColor = color;
}

styleTitle(
  overview,
  "PLM 项目标准/非标/差异与调研确认",
  "本工作簿是 AI 初步分析，不是正式需求或正式方案。先在每个项目的黄色列选择“初版可用/需要调优/补充资料后再审”；只有需要调整时再到明细页逐条维护。实际调研记录优先，调研业务表单仅作参考。",
  "N",
);
overview.getRange("A5:J6").values = [
  ["项目数", projects.length, "分析条目", items.length, "调研大纲", outline.length, "资料覆盖", coverage.length, "当前状态", "待人工确认"],
  ["有实际调研的项目", projects.filter((item) => item.has_actual_survey).length, "有合同/技术协议的项目", projects.filter((item) => item.has_contract_or_tech).length, "通用/未归属资料", analysis.unassigned_source_count || 0, "版本", analysis.version, "生成日期", new Date(analysis.generated_at)],
];
overview.getRange("A5:J6").format = {
  font: { name: FONT, size: 10, color: COLORS.text },
  verticalAlignment: "center",
  wrapText: true,
  borders: { preset: "outside", style: "thin", color: COLORS.border },
};
for (const cell of ["A5", "C5", "E5", "G5", "I5", "A6", "C6", "E6", "G6", "I6"]) {
  overview.getRange(cell).format.font = { name: FONT, size: 10, bold: true, color: COLORS.blue };
}
overview.getRange("J6").format.numberFormat = "yyyy-mm-dd";
overview.getRange("A8:N8").values = [[
  "项目编号", "项目", "AI摘要", "资料概况", "标准功能", "非标功能", "差异项", "待确认项", "证据成熟度", "项目结论", "调优方向/补充资料", "评审人", "评审日期", "处理状态",
]];
styleHeader(overview.getRange("A8:N8"));
const overviewStart = 9;
const overviewEnd = overviewStart + projects.length - 1;
overview.getRange(`A${overviewStart}:N${overviewEnd}`).values = projects.map((project) => [
  project.project_id,
  project.project_name,
  project.summary,
  sourceSummary(project),
  project.category_counts["标准功能"] || 0,
  project.category_counts["非标功能"] || 0,
  project.category_counts["差异项"] || 0,
  project.category_counts["待确认项"] || 0,
  project.has_actual_survey && project.has_contract_or_tech ? "较高" : project.has_actual_survey || project.has_contract_or_tech ? "中" : "初步",
  "待确认",
  "",
  "",
  null,
  "待处理",
]);
styleBody(overview.getRange(`A${overviewStart}:N${overviewEnd}`));
overview.getRange(`J${overviewStart}:M${overviewEnd}`).format.fill = COLORS.amber;
overview.getRange(`J${overviewStart}:J${overviewEnd}`).dataValidation = { rule: { type: "list", values: PROJECT_DECISIONS } };
overview.getRange(`M${overviewStart}:M${overviewEnd}`).format.numberFormat = "yyyy-mm-dd";
for (let row = overviewStart; row <= overviewEnd; row += 1) {
  overview.getRange(`N${row}`).formulas = [[`=IF(OR(J${row}="",J${row}="待确认"),"待处理",IF(OR(L${row}="",M${row}=""),"填写评审人/日期",IF(J${row}="需要调优","待调优",IF(J${row}="补充资料后再审","待补资料","已处理"))))`]];
}
overview.getRange(`N${overviewStart}:N${overviewEnd}`).conditionalFormats.addCustom(`=N${overviewStart}="已处理"`, { fill: COLORS.green, font: { bold: true, color: COLORS.greenText } });
overview.getRange(`N${overviewStart}:N${overviewEnd}`).conditionalFormats.addCustom(`=N${overviewStart}="待调优"`, { fill: COLORS.red, font: { bold: true, color: COLORS.redText } });
overview.getRange(`N${overviewStart}:N${overviewEnd}`).conditionalFormats.addCustom(`=N${overviewStart}="待补资料"`, { fill: COLORS.amber, font: { bold: true, color: "#7F6000" } });
overview.getRange("A:A").format.columnWidth = 10;
overview.getRange("B:B").format.columnWidth = 30;
overview.getRange("C:C").format.columnWidth = 58;
overview.getRange("D:D").format.columnWidth = 28;
overview.getRange("E:H").format.columnWidth = 12;
overview.getRange("I:I").format.columnWidth = 14;
overview.getRange("J:J").format.columnWidth = 18;
overview.getRange("K:K").format.columnWidth = 48;
overview.getRange("L:N").format.columnWidth = 17;
overview.getRange(`${overviewStart}:${overviewEnd}`).format.rowHeight = 84;
overview.freezePanes.freezeRows(8);
overview.freezePanes.freezeColumns(2);

const detailSheets = new Map([
  ["标准功能", standard],
  ["非标功能", nonstandard],
  ["差异项", gaps],
  ["待确认项", pending],
]);

const linkRanges = [];
for (const [category, sheet] of detailSheets.entries()) {
  const categoryItems = items.filter((item) => item.category === category);
  styleTitle(
    sheet,
    `${category} · AI 建议确认`,
    "黄色列需要人工维护。点击“打开证据”可查看原文位置和标准能力对照；如选择“修改后接受”或“退回”，请在人工修订/说明中写明最终意见。",
    "K",
  );
  sheet.getRange("A6:K6").values = [[
    "编号", "项目", "业务域", "AI建议", "判断依据", "建议动作", "置信度", "证据位置", "打开证据", "用户结论", "人工修订/说明",
  ]];
  styleHeader(sheet.getRange("A6:K6"));
  const start = 7;
  const end = start + categoryItems.length - 1;
  sheet.getRange(`A${start}:K${end}`).values = categoryItems.map((item) => [
    item.item_id,
    item.project_name,
    item.domain,
    item.title,
    item.basis,
    item.action,
    item.confidence,
    item.evidence_location,
    null,
    "待确认",
    "",
  ]);
  const formulas = categoryItems.map((item) => [`=HYPERLINK("${formulaEscape(item.evidence_link)}","打开证据 ►")`]);
  sheet.getRange(`I${start}:I${end}`).formulas = formulas;
  linkRanges.push({ sheet, address: `I${start}:I${end}`, formulas, values: categoryItems.map(() => ["打开证据 ►"]) });
  styleBody(sheet.getRange(`A${start}:K${end}`));
  sheet.getRange(`I${start}:I${end}`).format = {
    fill: COLORS.paleBlue,
    font: { name: FONT, size: 10, bold: true, color: "#0563C1", underline: "single" },
    horizontalAlignment: "center",
    verticalAlignment: "center",
  };
  sheet.getRange(`J${start}:K${end}`).format.fill = COLORS.amber;
  sheet.getRange(`J${start}:J${end}`).dataValidation = { rule: { type: "list", values: ITEM_DECISIONS } };
  applyDecisionFormatting(sheet, `J${start}:J${end}`, start);
  sheet.getRange("A:A").format.columnWidth = 11;
  sheet.getRange("B:B").format.columnWidth = 30;
  sheet.getRange("C:C").format.columnWidth = 20;
  sheet.getRange("D:D").format.columnWidth = 48;
  sheet.getRange("E:E").format.columnWidth = 56;
  sheet.getRange("F:F").format.columnWidth = 46;
  sheet.getRange("G:G").format.columnWidth = 12;
  sheet.getRange("H:H").format.columnWidth = 50;
  sheet.getRange("I:I").format.columnWidth = 16;
  sheet.getRange("J:J").format.columnWidth = 18;
  sheet.getRange("K:K").format.columnWidth = 50;
  sheet.getRange(`${start}:${end}`).format.rowHeight = 94;
  sheet.freezePanes.freezeRows(6);
  sheet.freezePanes.freezeColumns(2);
}

styleTitle(
  survey,
  "按项目推荐的调研大纲",
  "此页把现有资料中的差异和待确认问题转为可执行的访谈主题。建议按项目筛选后使用；黄色列用于记录是否采用以及你的调整意见。",
  "J",
);
survey.getRange("A6:J6").values = [[
  "编号", "项目", "顺序", "调研主题", "建议问题", "建议参与人", "预期产出", "为什么要问", "是否采用", "调整意见",
]];
styleHeader(survey.getRange("A6:J6"));
const surveyStart = 7;
const surveyEnd = surveyStart + outline.length - 1;
survey.getRange(`A${surveyStart}:J${surveyEnd}`).values = outline.map((item) => [
  item.outline_id,
  item.project_name,
  item.order,
  item.topic,
  item.questions,
  item.participants,
  item.expected_output,
  item.why,
  "待确认",
  "",
]);
styleBody(survey.getRange(`A${surveyStart}:J${surveyEnd}`));
survey.getRange(`I${surveyStart}:J${surveyEnd}`).format.fill = COLORS.amber;
survey.getRange(`I${surveyStart}:I${surveyEnd}`).dataValidation = { rule: { type: "list", values: ["待确认", "采用", "调整后采用", "不采用"] } };
survey.getRange("A:A").format.columnWidth = 13;
survey.getRange("B:B").format.columnWidth = 30;
survey.getRange("C:C").format.columnWidth = 8;
survey.getRange("D:D").format.columnWidth = 24;
survey.getRange("E:E").format.columnWidth = 64;
survey.getRange("F:F").format.columnWidth = 42;
survey.getRange("G:H").format.columnWidth = 46;
survey.getRange("I:I").format.columnWidth = 16;
survey.getRange("J:J").format.columnWidth = 48;
survey.getRange(`${surveyStart}:${surveyEnd}`).format.rowHeight = 88;
survey.freezePanes.freezeRows(6);
survey.freezePanes.freezeColumns(2);

styleTitle(
  sources,
  "资料覆盖与项目归属",
  "本轮共覆盖已解析的方案、标准能力、合同/技术协议、风险评估和真实调研记录。‘未归属/通用资料’主要是 20 份标准能力/调研模板，以及仍需确认项目归属的通用合同或招标协议。",
  "G",
);
sources.getRange("A6:G6").values = [["资料类别", "项目归属", "来源文件", "解析状态", "解析告警数", "打开原文", "归属状态"]];
styleHeader(sources.getRange("A6:G6"));
const sourceStart = 7;
const sourceEnd = sourceStart + coverage.length - 1;
sources.getRange(`A${sourceStart}:G${sourceEnd}`).values = coverage.map((item) => [
  item.source_type,
  item.project_name,
  item.source_name,
  item.parse_status,
  item.warning_count,
  null,
  item.is_assigned ? "已归属" : "通用/待归属",
]);
const sourceFormulas = coverage.map((item) => [item.original_url ? `=HYPERLINK("${formulaEscape(item.original_url)}","打开原文 ►")` : ""]);
sources.getRange(`F${sourceStart}:F${sourceEnd}`).formulas = sourceFormulas;
linkRanges.push({ sheet: sources, address: `F${sourceStart}:F${sourceEnd}`, formulas: sourceFormulas, values: coverage.map((item) => [item.original_url ? "打开原文 ►" : "未定位"]) });
styleBody(sources.getRange(`A${sourceStart}:G${sourceEnd}`));
sources.getRange(`F${sourceStart}:F${sourceEnd}`).format = {
  fill: COLORS.paleBlue,
  font: { name: FONT, size: 10, bold: true, color: "#0563C1", underline: "single" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
sources.getRange(`G${sourceStart}:G${sourceEnd}`).conditionalFormats.addCustom(`=G${sourceStart}="通用/待归属"`, { fill: COLORS.amber, font: { bold: true, color: "#7F6000" } });
sources.getRange("A:A").format.columnWidth = 24;
sources.getRange("B:B").format.columnWidth = 34;
sources.getRange("C:C").format.columnWidth = 72;
sources.getRange("D:E").format.columnWidth = 14;
sources.getRange("F:F").format.columnWidth = 16;
sources.getRange("G:G").format.columnWidth = 18;
sources.getRange(`${sourceStart}:${sourceEnd}`).format.rowHeight = 42;
sources.freezePanes.freezeRows(6);
sources.freezePanes.freezeColumns(2);

styleTitle(
  guide,
  "分类口径与使用说明",
  "优先级：真实调研记录 > 合同/技术协议 > 风险评估 > 既有方案 > 调研业务表单。标准能力是否满足，必须同时具备项目侧事实与标准侧证据；没有直接证据时不能把建议描述成已验证事实。",
  "E",
);
guide.getRange("A6:E6").values = [["分类", "含义", "判定依据", "人工确认重点", "确认后用途"]];
styleHeader(guide.getRange("A6:E6"));
guide.getRange("A7:E10").values = [
  ["标准功能", "标准产品可通过现有模块/配置完整承载的能力。", "项目有明确需求且标准能力库有直接证据。", "范围、前置条件、限制和是否仍需少量配置。", "确认后进入正式需求候选，不自动成为正式需求。"],
  ["非标功能", "需要二开、专用接口、专用算法/报表或特殊交付。", "必须存在明确的项目特定行为，不能仅因复杂或没找到证据就判非标。", "业务价值、最小范围、接口、维护和验收。", "确认后进入非标评估与变更/报价流程。"],
  ["差异项", "现状/目标与标准模型之间部分不一致或有特殊条件。", "项目事实与标准证据均存在，但覆盖不完整、规则冲突或环境不兼容。", "差异能否配置、是否需要改流程、是否升级为非标。", "确认后形成差异处理方案。"],
  ["待确认项", "资料不足、冲突、归属不清或必须由业务决策。", "缺少直接证据，或不同资料/部门意见不一致。", "明确唯一答案、责任人、截止时间和所需资料。", "确认前不得当作正式业务事实。"],
];
styleBody(guide.getRange("A7:E10"));
guide.getRange("A7:A10").format.font = { name: FONT, size: 10, bold: true, color: COLORS.blue };
guide.getRange("A:A").format.columnWidth = 18;
guide.getRange("B:E").format.columnWidth = 52;
guide.getRange("7:10").format.rowHeight = 76;
guide.getRange("A13:E17").values = [
  ["最省事的确认方式", "先看“项目总览”，每个项目只选一次项目结论。", "若选“需要调优”，再到对应明细页逐条修改。", "若选“补充资料后再审”，在调优方向列写缺什么。", "不用把原文复制进表格。"],
  ["证据定位", "明细页点击“打开证据”。", "浏览器中查看短摘录和来源定位。", "再点击“打开原文”进入本地文件。", "所有链接均为本地。"],
  ["真实调研", "面对面交流记录作为主要事实证据。", "调研表单只作问题提示。", "不能用空白模板替代客户表达。", "符合本项目既定规则。"],
  ["AI 输出", "本轮没有调用外部模型。", "结论由本地资料和既定分类规则形成。", "必须人工确认。", "确认历史应保留版本。"],
  ["资料缺口", "通用/待归属资料不强行归入项目。", "旧版 DOC 已在本地转换为分析副本。", "原文件未改动。", "客户资料不会提交 Git。"],
];
guide.getRange("A13:E17").format = {
  fill: COLORS.amber,
  font: { name: FONT, size: 10, color: "#7F6000" },
  wrapText: true,
  verticalAlignment: "top",
  borders: { preset: "all", style: "thin", color: COLORS.border },
};
guide.freezePanes.freezeRows(6);

workbook.recalculate();
await fs.mkdir(outputDir, { recursive: true });

for (const linkRange of linkRanges) {
  linkRange.sheet.getRange(linkRange.address).values = linkRange.values;
}

const previewSpecs = [
  ["项目总览", `A1:N${Math.min(overviewEnd, 20)}`, "preview-项目总览.png"],
  ["标准功能", "A1:K18", "preview-标准功能.png"],
  ["非标功能", "A1:K18", "preview-非标功能.png"],
  ["差异项", "A1:K18", "preview-差异项.png"],
  ["待确认项", "A1:K18", "preview-待确认项.png"],
  ["推荐调研大纲", "A1:J18", "preview-调研大纲.png"],
  ["资料覆盖", "A1:G20", "preview-资料覆盖.png"],
  ["分类口径", "A1:E17", "preview-分类口径.png"],
];
for (const [sheetName, range, fileName] of previewSpecs) {
  const preview = await workbook.render({ sheetName, range, scale: 1.05, format: "png" });
  await fs.writeFile(path.join(outputDir, fileName), new Uint8Array(await preview.arrayBuffer()));
}

for (const linkRange of linkRanges) {
  linkRange.sheet.getRange(linkRange.address).formulas = linkRange.formulas;
}
workbook.recalculate();

const outputPath = path.join(outputDir, "PLM项目标准非标差异与调研确认-R1.xlsx");
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

const saved = await SpreadsheetFile.importXlsx(await FileBlob.load(outputPath));
const validation = [];
for (const [sheetName, range, rows, cols] of [
  ["项目总览", "A1:N20", 20, 14],
  ["标准功能", "A1:K16", 16, 11],
  ["非标功能", "A1:K16", 16, 11],
  ["差异项", "A1:K16", 16, 11],
  ["待确认项", "A1:K16", 16, 11],
  ["推荐调研大纲", "A1:J16", 16, 10],
  ["资料覆盖", "A1:G16", 16, 7],
  ["分类口径", "A1:E17", 17, 5],
]) {
  const inspected = await saved.inspect({
    kind: "table",
    range: `${sheetName}!${range}`,
    include: "values,formulas",
    tableMaxRows: rows,
    tableMaxCols: cols,
    maxChars: 22000,
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

const testOverview = saved.worksheets.getItem("项目总览");
testOverview.getRange("J9").values = [["需要调优"]];
testOverview.getRange("K9").values = [["回归测试：补充接口字段"]];
testOverview.getRange("L9").values = [["回归测试"]];
testOverview.getRange("M9").values = [[new Date("2026-09-21T00:00:00+08:00")]];
saved.recalculate();
validation.push((await saved.inspect({
  kind: "table",
  range: "项目总览!I8:N9",
  include: "values,formulas",
  tableMaxRows: 2,
  tableMaxCols: 6,
  maxChars: 5000,
})).ndjson);
const testDetail = saved.worksheets.getItem("标准功能");
testDetail.getRange("J7").values = [["修改后接受"]];
testDetail.getRange("K7").values = [["回归测试：调整为一期范围"]];
saved.recalculate();
validation.push((await saved.inspect({
  kind: "table",
  range: "标准功能!I6:K7",
  include: "values,formulas",
  tableMaxRows: 2,
  tableMaxCols: 3,
  maxChars: 4000,
})).ndjson);

await fs.writeFile(path.join(outputDir, "artifact-tool-validation.ndjson"), validation.join("\n"), "utf8");
await fs.writeFile(path.join(outputDir, "workbook-result.json"), JSON.stringify({
  status: "AWAITING_HUMAN_CONFIRMATION",
  output_path: outputPath,
  project_count: projects.length,
  item_count: items.length,
  outline_count: outline.length,
  source_count: coverage.length,
  preview_count: previewSpecs.length,
}, null, 2), "utf8");

console.log(JSON.stringify({
  status: "AWAITING_HUMAN_CONFIRMATION",
  outputPath,
  projectCount: projects.length,
  itemCount: items.length,
  outlineCount: outline.length,
  sourceCount: coverage.length,
  previewCount: previewSpecs.length,
}));
