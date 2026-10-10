import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";


const [packagePath, outputDir] = process.argv.slice(2);
if (!packagePath || !outputDir) {
  throw new Error("Usage: node build_final_delivery_workbook.mjs <package.json> <output-dir>");
}

const payload = JSON.parse(await fs.readFile(packagePath, "utf8"));
const projects = payload.projects;
const items = payload.delivery_items;
const specialties = payload.specialty_items;
const formalizations = payload.formalization_items;
const survey = payload.survey_outline;

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
const overview = workbook.worksheets.add("交付总览");
const mapping = workbook.worksheets.add("需求与方案");
const route = workbook.worksheets.add("实施路线");
const specialty = workbook.worksheets.add("专项清单");
const formalization = workbook.worksheets.add("正式化待办");
const surveySheet = workbook.worksheets.add("调研大纲");

overview.tabColor = COLORS.navy;
mapping.tabColor = "#70AD47";
route.tabColor = "#5B9BD5";
specialty.tabColor = "#ED7D31";
formalization.tabColor = "#FFC000";
surveySheet.tabColor = "#A5A5A5";
for (const sheet of [overview, mapping, route, specialty, formalization, surveySheet]) {
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

function linkStyle(range) {
  range.format = {
    fill: COLORS.paleBlue,
    font: { name: FONT, size: 10, bold: true, color: "#0563C1", underline: "single" },
    horizontalAlignment: "center",
    verticalAlignment: "center",
  };
}

function formulaEscape(value) {
  return String(value || "").replaceAll('"', '""');
}

const counts = {
  standard: items.filter((row) => row.category === "标准功能").length,
  custom: items.filter((row) => row.category === "非标功能").length,
  difference: items.filter((row) => row.category === "差异项").length,
  pending: items.filter((row) => row.category === "待确认项").length,
  high: items.filter((row) => row.risk === "高").length,
};

title(
  overview,
  "第一批项目需求与解决方案交付包",
  "整合内部需求评审稿、解决方案草案、专项设计、实施路线和调研大纲。当前可用于内部交接与项目准备，不代表正式需求或正式方案。",
  "L",
);
overview.getRange("A5:L5").values = [[
  "项目", projects.length,
  "需求与方案", items.length,
  "专项设计", specialties.length,
  "正式化待办", formalizations.length,
  "调研主题", survey.length,
  "正式对象", 0,
]];
overview.getRange("A5:L5").format = {
  fill: COLORS.gray,
  font: { name: FONT, size: 10, color: COLORS.text },
  verticalAlignment: "center",
  borders: { preset: "outside", style: "thin", color: COLORS.border },
};
for (const cell of ["A5", "C5", "E5", "G5", "I5", "K5"]) {
  overview.getRange(cell).format.font = { name: FONT, size: 10, bold: true, color: COLORS.blue };
}
for (const cell of ["B5", "D5", "F5", "H5", "J5", "L5"]) {
  overview.getRange(cell).format.font = { name: FONT, size: 12, bold: true, color: COLORS.navy };
  overview.getRange(cell).format.horizontalAlignment = "center";
}

overview.getRange("A8:L8").values = [[
  "项目", "需求", "标准功能", "非标功能", "差异项", "正式化待办", "P0", "高风险", "专项", "内部交付", "正式化状态", "建议下一步",
]];
header(overview.getRange("A8:L8"));
const projectStart = 9;
const projectEnd = projectStart + projects.length - 1;
overview.getRange(`A${projectStart}:L${projectEnd}`).values = projects.map((row) => [
  row.project_name,
  row.requirement_count,
  row.standard_count,
  row.custom_count,
  row.difference_count,
  row.formalization_count,
  row.p0_count,
  row.high_risk_count,
  row.specialty_count,
  "内部交付草案已完成",
  "受 Phase 0 与 Review Gate 阻塞",
  row.recommended_next,
]);
body(overview.getRange(`A${projectStart}:L${projectEnd}`));
overview.getRange(`J${projectStart}:J${projectEnd}`).format = {
  fill: COLORS.green,
  font: { name: FONT, size: 10, bold: true, color: COLORS.greenText },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
overview.getRange(`K${projectStart}:K${projectEnd}`).format = {
  fill: COLORS.amber,
  font: { name: FONT, size: 10, bold: true, color: COLORS.amberText },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
};
overview.getRange("A:A").format.columnWidth = 34;
overview.getRange("B:I").format.columnWidth = 12;
overview.getRange("J:K").format.columnWidth = 27;
overview.getRange("L:L").format.columnWidth = 62;
overview.getRange(`${projectStart}:${projectEnd}`).format.rowHeight = 72;

overview.getRange("A17:L22").values = [
  ["交付批次", "名称", "对象", "进入条件", "完成证据", "", "", "", "", "", "", ""],
  ["W0", "范围与决策收敛", formalizations.length, "责任方形成唯一书面结论", "正式确认记录、影响分析和 TraceLink", "", "", "", "", "", "", ""],
  ["W1", "标准能力配置", counts.standard, "需求范围与验收样例稳定", "配置记录、用例和评审记录", "", "", "", "", "", "", ""],
  ["W2", "差异验证与治理", counts.difference, "现状、目标和差异处置规则明确", "差异结论、例外和治理记录", "", "", "", "", "", "", ""],
  ["W3", "非标与专项实现", counts.custom, "接口、迁移、权限或领域前置齐备", "专项契约、测试、对账和审计记录", "", "", "", "", "", "", ""],
  ["W4", "验收、交接与正式化", items.length, "前序批次完成且 Phase/Gate 条件满足", "Review 记录、正式版本和完整追溯链", "", "", "", "", "", "", ""],
];
for (let row = 17; row <= 22; row += 1) {
  overview.mergeCells(`E${row}:L${row}`);
}
overview.getRange("A17:L22").format = {
  font: { name: FONT, size: 10, color: COLORS.text },
  verticalAlignment: "center",
  wrapText: true,
  borders: { bottom: { style: "thin", color: COLORS.border } },
};
overview.getRange("A17:L17").format = {
  fill: COLORS.gray,
  font: { name: FONT, size: 10, bold: true, color: COLORS.blue },
};
overview.getRange("17:22").format.rowHeight = 36;
overview.freezePanes.freezeRows(8);
overview.freezePanes.freezeColumns(1);

title(
  mapping,
  "需求与方案追溯矩阵",
  "40 条内部需求与 40 条方案一一对应。证据链接定位原始材料；状态列明确阻止把草案误读为正式业务事实。",
  "R",
);
mapping.getRange("A6:R6").values = [[
  "交付编号", "项目", "需求编号", "方案编号", "优先级", "风险", "需求类型", "领域", "需求名称", "能力匹配", "实施批次", "实现方式", "方案名称", "方案摘要", "验收方案", "明确排除", "打开证据", "正式状态",
]];
header(mapping.getRange("A6:R6"));
const mappingStart = 7;
const mappingEnd = mappingStart + items.length - 1;
mapping.getRange(`A${mappingStart}:R${mappingEnd}`).values = items.map((row) => [
  row.delivery_id,
  row.project_name,
  row.requirement_id,
  row.solution_id,
  row.priority,
  row.risk,
  row.category,
  row.domain,
  row.requirement_title,
  row.capability_match,
  `${row.delivery_wave} ${row.delivery_wave_name}`,
  row.build_mode,
  row.solution_name,
  row.solution_outline,
  row.acceptance_plan,
  row.explicit_exclusion,
  null,
  `${row.requirement_status} / ${row.solution_status}`,
]);
const mappingLinks = items.map((row) => [`=HYPERLINK("${formulaEscape(row.evidence_link)}","打开证据")`]);
mapping.getRange(`Q${mappingStart}:Q${mappingEnd}`).formulas = mappingLinks;
body(mapping.getRange(`A${mappingStart}:R${mappingEnd}`));
linkStyle(mapping.getRange(`Q${mappingStart}:Q${mappingEnd}`));
mapping.getRange(`E${mappingStart}:E${mappingEnd}`).conditionalFormats.addCustom(
  `=E${mappingStart}="P0"`,
  { fill: COLORS.red, font: { bold: true, color: COLORS.redText } },
);
mapping.getRange(`F${mappingStart}:F${mappingEnd}`).conditionalFormats.addCustom(
  `=F${mappingStart}="高"`,
  { fill: COLORS.red, font: { bold: true, color: COLORS.redText } },
);
mapping.getRange(`R${mappingStart}:R${mappingEnd}`).format = {
  fill: COLORS.gray,
  font: { name: FONT, size: 9, bold: true, color: COLORS.muted },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
};
mapping.tables.add(`A6:R${mappingEnd}`, true, "FinalRequirementSolutionTable").style = "TableStyleMedium4";
mapping.getRange("A:A").format.columnWidth = 15;
mapping.getRange("B:B").format.columnWidth = 34;
mapping.getRange("C:D").format.columnWidth = 17;
mapping.getRange("E:H").format.columnWidth = 12;
mapping.getRange("I:I").format.columnWidth = 48;
mapping.getRange("J:M").format.columnWidth = 28;
mapping.getRange("N:P").format.columnWidth = 62;
mapping.getRange("Q:Q").format.columnWidth = 15;
mapping.getRange("R:R").format.columnWidth = 34;
mapping.getRange(`${mappingStart}:${mappingEnd}`).format.rowHeight = 102;
mapping.freezePanes.freezeRows(6);
mapping.freezePanes.freezeColumns(4);

title(
  route,
  "实施路线与验收证据",
  "按照 W0-W4 批次推进。每条记录都给出进入条件、完成证据、依赖和专项类型，便于转换为后续实施计划。",
  "N",
);
route.getRange("A6:N6").values = [[
  "项目", "批次", "需求编号", "需求名称", "优先级", "风险", "实现方式", "专项类型", "涉及组件", "进入条件", "依赖/前提", "完成证据", "交付状态", "下一关口",
]];
header(route.getRange("A6:N6"));
const routeStart = 7;
const routeEnd = routeStart + items.length - 1;
route.getRange(`A${routeStart}:N${routeEnd}`).values = items.map((row) => [
  row.project_name,
  `${row.delivery_wave} ${row.delivery_wave_name}`,
  row.requirement_id,
  row.requirement_title,
  row.priority,
  row.risk,
  row.build_mode,
  row.specialty_types.join("、") || "无独立专项",
  row.component,
  row.entry_condition,
  row.dependency,
  row.completion_evidence,
  row.delivery_status,
  row.delivery_wave === "W0" ? "正式确认与 Review" : "W4 验收与正式化",
]);
body(route.getRange(`A${routeStart}:N${routeEnd}`));
route.getRange(`B${routeStart}:B${routeEnd}`).format = {
  fill: COLORS.paleBlue,
  font: { name: FONT, size: 10, bold: true, color: COLORS.blue },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
};
route.tables.add(`A6:N${routeEnd}`, true, "DeliveryRouteTable").style = "TableStyleMedium2";
route.getRange("A:A").format.columnWidth = 34;
route.getRange("B:B").format.columnWidth = 23;
route.getRange("C:C").format.columnWidth = 17;
route.getRange("D:D").format.columnWidth = 48;
route.getRange("E:H").format.columnWidth = 14;
route.getRange("I:I").format.columnWidth = 38;
route.getRange("J:L").format.columnWidth = 62;
route.getRange("M:N").format.columnWidth = 28;
route.getRange(`${routeStart}:${routeEnd}`).format.rowHeight = 94;
route.freezePanes.freezeRows(6);
route.freezePanes.freezeColumns(3);

title(
  specialty,
  "接口、迁移与权限专项清单",
  "21 项专项设计从需求与方案矩阵派生。当前是设计输入，不是冻结的接口、迁移或权限基线。",
  "J",
);
specialty.getRange("A6:J6").values = [[
  "专项编号", "项目", "类型", "需求编号", "方案编号", "对应需求", "设计草案", "进入条件", "验收重点", "打开证据",
]];
header(specialty.getRange("A6:J6"));
const specialtyStart = 7;
const specialtyEnd = specialtyStart + specialties.length - 1;
specialty.getRange(`A${specialtyStart}:J${specialtyEnd}`).values = specialties.map((row) => [
  row.specialty_id,
  row.project_name,
  row.type,
  row.requirement_id,
  row.solution_id,
  row.title,
  row.design,
  row.entry_condition,
  row.acceptance,
  null,
]);
const specialtyLinks = specialties.map((row) => [`=HYPERLINK("${formulaEscape(row.evidence_link)}","打开证据")`]);
specialty.getRange(`J${specialtyStart}:J${specialtyEnd}`).formulas = specialtyLinks;
body(specialty.getRange(`A${specialtyStart}:J${specialtyEnd}`));
linkStyle(specialty.getRange(`J${specialtyStart}:J${specialtyEnd}`));
specialty.tables.add(`A6:J${specialtyEnd}`, true, "FinalSpecialtyTable").style = "TableStyleMedium2";
specialty.getRange("A:A").format.columnWidth = 30;
specialty.getRange("B:B").format.columnWidth = 34;
specialty.getRange("C:C").format.columnWidth = 21;
specialty.getRange("D:E").format.columnWidth = 17;
specialty.getRange("F:F").format.columnWidth = 48;
specialty.getRange("G:I").format.columnWidth = 62;
specialty.getRange("J:J").format.columnWidth = 15;
specialty.getRange(`${specialtyStart}:${specialtyEnd}`).format.rowHeight = 96;
specialty.freezePanes.freezeRows(6);
specialty.freezePanes.freezeColumns(2);

title(
  formalization,
  "工作基线正式化待办",
  "10 条 AI 代决策已支持内部继续工作，但仍需责任方书面确认、影响分析和 Review Engine 才能成为正式业务事实。",
  "L",
);
formalization.getRange("A6:L6").values = [[
  "决策编号", "项目", "需求编号", "问题", "工作基线", "纳入范围", "明确排除", "验收依据", "风险", "当前状态", "正式化动作", "打开证据",
]];
header(formalization.getRange("A6:L6"));
const formalStart = 7;
const formalEnd = formalStart + formalizations.length - 1;
formalization.getRange(`A${formalStart}:L${formalEnd}`).values = formalizations.map((row) => [
  row.decision_id,
  row.project_name,
  row.requirement_id,
  row.issue,
  row.working_baseline,
  row.included_scope,
  row.explicit_exclusion,
  row.acceptance_basis,
  row.risk,
  row.formalization_status,
  row.formalization_action,
  null,
]);
const formalLinks = formalizations.map((row) => [`=HYPERLINK("${formulaEscape(row.evidence_link)}","打开证据")`]);
formalization.getRange(`L${formalStart}:L${formalEnd}`).formulas = formalLinks;
body(formalization.getRange(`A${formalStart}:L${formalEnd}`));
linkStyle(formalization.getRange(`L${formalStart}:L${formalEnd}`));
formalization.getRange(`J${formalStart}:J${formalEnd}`).format = {
  fill: COLORS.amber,
  font: { name: FONT, size: 10, bold: true, color: COLORS.amberText },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
};
formalization.tables.add(`A6:L${formalEnd}`, true, "FormalizationBacklogTable").style = "TableStyleMedium9";
formalization.getRange("A:A").format.columnWidth = 22;
formalization.getRange("B:B").format.columnWidth = 34;
formalization.getRange("C:C").format.columnWidth = 17;
formalization.getRange("D:I").format.columnWidth = 58;
formalization.getRange("J:J").format.columnWidth = 28;
formalization.getRange("K:K").format.columnWidth = 58;
formalization.getRange("L:L").format.columnWidth = 15;
formalization.getRange(`${formalStart}:${formalEnd}`).format.rowHeight = 112;
formalization.freezePanes.freezeRows(6);
formalization.freezePanes.freezeColumns(3);

title(
  surveySheet,
  "推荐调研大纲",
  "每个项目按六个主题组织后续沟通。业务表单只作为参考，问题顺序与重点以实际调研记录、需求和证据为主。",
  "H",
);
surveySheet.getRange("A6:H6").values = [[
  "大纲编号", "项目", "顺序", "主题", "重点事项", "调研目标", "预期输出", "状态",
]];
header(surveySheet.getRange("A6:H6"));
const surveyStart = 7;
const surveyEnd = surveyStart + survey.length - 1;
const projectNameIndex = new Map(projects.map((row) => [row.project_id, row.project_name]));
surveySheet.getRange(`A${surveyStart}:H${surveyEnd}`).values = survey.map((row) => [
  row.outline_id,
  projectNameIndex.get(row.project_id),
  row.sequence,
  row.topic,
  row.focus_items,
  row.objective,
  row.expected_output,
  row.status,
]);
body(surveySheet.getRange(`A${surveyStart}:H${surveyEnd}`));
surveySheet.tables.add(`A6:H${surveyEnd}`, true, "SurveyOutlineTable").style = "TableStyleMedium4";
surveySheet.getRange("A:A").format.columnWidth = 18;
surveySheet.getRange("B:B").format.columnWidth = 34;
surveySheet.getRange("C:C").format.columnWidth = 10;
surveySheet.getRange("D:D").format.columnWidth = 24;
surveySheet.getRange("E:G").format.columnWidth = 62;
surveySheet.getRange("H:H").format.columnWidth = 28;
surveySheet.getRange(`${surveyStart}:${surveyEnd}`).format.rowHeight = 88;
surveySheet.freezePanes.freezeRows(6);
surveySheet.freezePanes.freezeColumns(2);

workbook.recalculate();
await fs.mkdir(outputDir, { recursive: true });

const linkRanges = [
  { sheet: mapping, address: `Q${mappingStart}:Q${mappingEnd}`, formulas: mappingLinks, values: items.map(() => ["打开证据"]) },
  { sheet: specialty, address: `J${specialtyStart}:J${specialtyEnd}`, formulas: specialtyLinks, values: specialties.map(() => ["打开证据"]) },
  { sheet: formalization, address: `L${formalStart}:L${formalEnd}`, formulas: formalLinks, values: formalizations.map(() => ["打开证据"]) },
];
for (const linkRange of linkRanges) {
  linkRange.sheet.getRange(linkRange.address).values = linkRange.values;
}

const previews = [
  ["交付总览", "A1:L22", "preview-交付总览.png"],
  ["需求与方案", "A1:R18", "preview-需求与方案.png"],
  ["实施路线", "A1:N18", "preview-实施路线.png"],
  ["专项清单", "A1:J18", "preview-专项清单.png"],
  ["正式化待办", "A1:L16", "preview-正式化待办.png"],
  ["调研大纲", "A1:H18", "preview-调研大纲.png"],
];
for (const [sheetName, range, fileName] of previews) {
  const preview = await workbook.render({ sheetName, range, scale: 1.05, format: "png" });
  await fs.writeFile(path.join(outputDir, fileName), new Uint8Array(await preview.arrayBuffer()));
}
for (const linkRange of linkRanges) {
  linkRange.sheet.getRange(linkRange.address).formulas = linkRange.formulas;
}
workbook.recalculate();

const outputPath = path.join(outputDir, "第一批项目需求与解决方案交付包-R6.xlsx");
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

const saved = await SpreadsheetFile.importXlsx(await FileBlob.load(outputPath));
const validation = [];
for (const [sheetName, range, rows, cols] of [
  ["交付总览", "A1:L22", 22, 12],
  ["需求与方案", "A1:R18", 18, 18],
  ["实施路线", "A1:N18", 18, 14],
  ["专项清单", "A1:J18", 18, 10],
  ["正式化待办", "A1:L16", 16, 12],
  ["调研大纲", "A1:H18", 18, 8],
]) {
  validation.push((await saved.inspect({
    kind: "table",
    range: `${sheetName}!${range}`,
    include: "values,formulas",
    tableMaxRows: rows,
    tableMaxCols: cols,
    maxChars: 32000,
  })).ndjson);
}
validation.push((await saved.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 300 },
  maxChars: 12000,
})).ndjson);
for (const [sheetId, range, count] of [
  ["需求与方案", `Q${mappingStart}:Q${mappingEnd}`, items.length],
  ["专项清单", `J${specialtyStart}:J${specialtyEnd}`, specialties.length],
  ["正式化待办", `L${formalStart}:L${formalEnd}`, formalizations.length],
]) {
  validation.push((await saved.inspect({
    kind: "formula",
    sheetId,
    range,
    maxChars: 18000,
    options: { maxResults: count },
  })).ndjson);
}

await fs.writeFile(path.join(outputDir, "artifact-tool-validation.ndjson"), validation.join("\n"), "utf8");
await fs.writeFile(path.join(outputDir, "workbook-result.json"), JSON.stringify({
  status: payload.status,
  output_path: outputPath,
  project_count: projects.length,
  delivery_item_count: items.length,
  standard_count: counts.standard,
  custom_count: counts.custom,
  difference_count: counts.difference,
  formalization_count: formalizations.length,
  specialty_count: specialties.length,
  survey_outline_count: survey.length,
  high_risk_count: counts.high,
  evidence_link_count: mappingLinks.length + specialtyLinks.length + formalLinks.length,
  preview_count: previews.length,
}, null, 2), "utf8");

console.log(JSON.stringify({
  status: payload.status,
  outputPath,
  projectCount: projects.length,
  deliveryItemCount: items.length,
  standardCount: counts.standard,
  customCount: counts.custom,
  differenceCount: counts.difference,
  formalizationCount: formalizations.length,
  specialtyCount: specialties.length,
  surveyOutlineCount: survey.length,
  highRiskCount: counts.high,
  evidenceLinkCount: mappingLinks.length + specialtyLinks.length + formalLinks.length,
  previewCount: previews.length,
}));
