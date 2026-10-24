import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";


const [packagePath, outputDir] = process.argv.slice(2);
if (!packagePath || !outputDir) {
  throw new Error("Usage: node build_solution_draft_workbook.mjs <package.json> <output-dir>");
}

const payload = JSON.parse(await fs.readFile(packagePath, "utf8"));
const projects = payload.projects;
const solutions = payload.solutions;
const interfaceIds = new Set(payload.interface_specs);
const migrationIds = new Set(payload.migration_specs);
const permissionIds = new Set(payload.permission_designs);

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
const overview = workbook.worksheets.add("方案总览");
const mapping = workbook.worksheets.add("需求方案映射");
const specialty = workbook.worksheets.add("专项设计");
const guide = workbook.worksheets.add("使用边界");
overview.tabColor = COLORS.navy;
mapping.tabColor = "#70AD47";
specialty.tabColor = "#ED7D31";
guide.tabColor = "#A5A5A5";
for (const sheet of [overview, mapping, specialty, guide]) {
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

const standardCount = solutions.filter((row) => row.build_mode === "标准配置").length;
const customCount = solutions.filter((row) => row.build_mode.includes("非标")).length;
const differenceCount = solutions.filter((row) => row.requirement_category === "差异项").length;
const workingCount = solutions.filter((row) => row.requirement_category === "待确认项").length;
const highRiskCount = solutions.filter((row) => row.risk === "高").length;

title(
  overview,
  "第一批项目解决方案草案",
  "40 条内部需求评审稿已形成一一对应的解决方案草案，覆盖标准配置、非标扩展、接口、迁移、权限和差异治理。所有方案仍为内部草案。",
  "K",
);
overview.getRange("A5:K5").values = [[
  "项目", projects.length,
  "方案草案", solutions.length,
  "标准配置", standardCount,
  "非标实现", customCount,
  "差异项", differenceCount,
  "正式方案 0",
]];
overview.getRange("A5:K5").format = {
  fill: COLORS.gray,
  font: { name: FONT, size: 10, color: COLORS.text },
  verticalAlignment: "center",
  borders: { preset: "outside", style: "thin", color: COLORS.border },
};
for (const cell of ["A5", "C5", "E5", "G5", "I5", "K5"]) {
  overview.getRange(cell).format.font = { name: FONT, size: 10, bold: true, color: COLORS.blue };
}
for (const cell of ["B5", "D5", "F5", "H5", "J5"]) {
  overview.getRange(cell).format.font = { name: FONT, size: 12, bold: true, color: COLORS.navy };
  overview.getRange(cell).format.horizontalAlignment = "center";
}

overview.getRange("A8:K8").values = [[
  "项目", "方案数", "标准配置", "非标实现", "接口专项", "迁移专项", "治理专项", "P0", "高风险", "内部状态", "下一动作",
]];
header(overview.getRange("A8:K8"));
const projectStart = 9;
const projectEnd = projectStart + projects.length - 1;
overview.getRange(`A${projectStart}:K${projectEnd}`).values = projects.map((row) => [
  row.project_name,
  row.solution_count,
  row.standard_count,
  row.custom_count,
  row.integration_count,
  row.data_count,
  row.governance_count,
  row.p0_count,
  row.high_risk_count,
  "内部方案草案已生成",
  row.next_action,
]);
body(overview.getRange(`A${projectStart}:K${projectEnd}`));
overview.getRange(`J${projectStart}:J${projectEnd}`).format = {
  fill: COLORS.green,
  font: { name: FONT, size: 10, bold: true, color: COLORS.greenText },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
overview.getRange("A:A").format.columnWidth = 34;
overview.getRange("B:I").format.columnWidth = 12;
overview.getRange("J:J").format.columnWidth = 25;
overview.getRange("K:K").format.columnWidth = 64;
overview.getRange(`${projectStart}:${projectEnd}`).format.rowHeight = 72;

overview.getRange("A17:K22").values = [
  ["方案类型", "数量", "设计原则", "", "", "", "", "", "", "", ""],
  ["标准配置", standardCount, "复用标准能力，通过配置、流程、权限和模板启用；不为标准功能复制二开模块。", "", "", "", "", "", "", "", ""],
  ["非标实现", customCount, "接口走独立适配层，领域扩展走模块内 Application Service；保留版本、Trace 和审计。", "", "", "", "", "", "", "", ""],
  ["差异处理", differenceCount, "优先流程调整、配置和治理；只有标准能力无法覆盖且有验收依据时才进入扩展。", "", "", "", "", "", "", "", ""],
  ["工作基线", workingCount, "保留 AI 代决策范围、明确排除和回滚路径，不描述为客户或合同正式结论。", "", "", "", "", "", "", "", ""],
  ["高风险", highRiskCount, "主数据、迁移、外部接口、合同和交付责任必须在正式方案中保留专项控制。", "", "", "", "", "", "", "", ""],
];
for (const row of [17, 18, 19, 20, 21, 22]) {
  overview.mergeCells(`C${row}:K${row}`);
}
overview.getRange("A17:K22").format = {
  font: { name: FONT, size: 10, color: COLORS.text },
  verticalAlignment: "center",
  wrapText: true,
  borders: { bottom: { style: "thin", color: COLORS.border } },
};
overview.getRange("A17:K17").format = {
  fill: COLORS.gray,
  font: { name: FONT, size: 10, bold: true, color: COLORS.blue },
};
overview.getRange("17:22").format.rowHeight = 34;
overview.freezePanes.freezeRows(8);
overview.freezePanes.freezeColumns(1);

title(
  mapping,
  "需求方案映射",
  "每条需求评审稿对应一个内部解决方案草案。点击“打开证据”可回到原始资料；正式 Solution 仍需 Requirement Review、Solution Review 和 Gate。",
  "R",
);
mapping.getRange("A6:R6").values = [[
  "方案编号", "项目", "需求编号", "优先级", "风险", "需求类型", "需求名称", "实现方式", "方案类型", "方案名称", "涉及组件", "方案摘要", "验收方案", "明确排除", "依赖/前提", "打开证据", "方案状态", "正式状态",
]];
header(mapping.getRange("A6:R6"));
const mappingStart = 7;
const mappingEnd = mappingStart + solutions.length - 1;
mapping.getRange(`A${mappingStart}:R${mappingEnd}`).values = solutions.map((row) => [
  row.solution_id,
  row.project_name,
  row.requirement_id,
  row.priority,
  row.risk,
  row.requirement_category,
  row.requirement_title,
  row.build_mode,
  row.archetype,
  row.solution_name,
  row.component,
  row.solution_outline,
  row.acceptance_plan,
  row.explicit_exclusion,
  row.dependency,
  null,
  row.status,
  row.formal_status,
]);
const mappingLinks = solutions.map((row) => [
  `=HYPERLINK("${formulaEscape(row.evidence_link)}","打开证据")`,
]);
mapping.getRange(`P${mappingStart}:P${mappingEnd}`).formulas = mappingLinks;
body(mapping.getRange(`A${mappingStart}:R${mappingEnd}`));
mapping.getRange(`P${mappingStart}:P${mappingEnd}`).format = {
  fill: COLORS.paleBlue,
  font: { name: FONT, size: 10, bold: true, color: "#0563C1", underline: "single" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
mapping.getRange(`D${mappingStart}:D${mappingEnd}`).conditionalFormats.addCustom(
  `=D${mappingStart}="P0"`,
  { fill: COLORS.red, font: { bold: true, color: COLORS.redText } },
);
mapping.getRange(`E${mappingStart}:E${mappingEnd}`).conditionalFormats.addCustom(
  `=E${mappingStart}="高"`,
  { fill: COLORS.red, font: { bold: true, color: COLORS.redText } },
);
mapping.getRange(`R${mappingStart}:R${mappingEnd}`).format = {
  fill: COLORS.gray,
  font: { name: FONT, size: 10, bold: true, color: COLORS.muted },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
mapping.tables.add(`A6:R${mappingEnd}`, true, "RequirementSolutionMapTable").style = "TableStyleMedium4";
mapping.getRange("A:A").format.columnWidth = 16;
mapping.getRange("B:B").format.columnWidth = 34;
mapping.getRange("C:C").format.columnWidth = 17;
mapping.getRange("D:F").format.columnWidth = 12;
mapping.getRange("G:G").format.columnWidth = 48;
mapping.getRange("H:J").format.columnWidth = 30;
mapping.getRange("K:K").format.columnWidth = 38;
mapping.getRange("L:O").format.columnWidth = 62;
mapping.getRange("P:P").format.columnWidth = 15;
mapping.getRange("Q:R").format.columnWidth = 28;
mapping.getRange(`${mappingStart}:${mappingEnd}`).format.rowHeight = 100;
mapping.freezePanes.freezeRows(6);
mapping.freezePanes.freezeColumns(3);

const specialRows = [];
for (const row of solutions) {
  if (interfaceIds.has(row.solution_id)) {
    specialRows.push({
      spec_id: `IF-${row.solution_id}`,
      project_name: row.project_name,
      solution_id: row.solution_id,
      type: "InterfaceSpec 草案",
      requirement_title: row.requirement_title,
      content: row.interface_spec,
      control: "统一适配层、凭据隔离、幂等、超时/重试和审计。",
      acceptance: row.acceptance_plan,
      evidence_link: row.evidence_link,
    });
  }
  if (migrationIds.has(row.solution_id)) {
    specialRows.push({
      spec_id: `MIG-${row.solution_id}`,
      project_name: row.project_name,
      solution_id: row.solution_id,
      type: "MigrationSpec 草案",
      requirement_title: row.requirement_title,
      content: row.migration_spec,
      control: "分批、可重跑、Hash 校验、版本保留和失败清单。",
      acceptance: row.acceptance_plan,
      evidence_link: row.evidence_link,
    });
  }
  if (permissionIds.has(row.solution_id)) {
    specialRows.push({
      spec_id: `PERM-${row.solution_id}`,
      project_name: row.project_name,
      solution_id: row.solution_id,
      type: "PermissionDesign 草案",
      requirement_title: row.requirement_title,
      content: row.permission_design,
      control: "默认拒绝、ProjectId 隔离、同口径导出和不可删除审计。",
      acceptance: row.acceptance_plan,
      evidence_link: row.evidence_link,
    });
  }
}

title(
  specialty,
  "接口、迁移与权限专项",
  "仅列出需要结构化专项设计的方案。每一项都保留需求、方案和证据追溯；当前内容是设计草案，不是冻结的接口、迁移或权限基线。",
  "I",
);
specialty.getRange("A6:I6").values = [[
  "专项编号", "项目", "方案编号", "专项类型", "对应需求", "设计草案", "控制措施", "验收重点", "打开证据",
]];
header(specialty.getRange("A6:I6"));
const specialStart = 7;
const specialEnd = specialStart + specialRows.length - 1;
specialty.getRange(`A${specialStart}:I${specialEnd}`).values = specialRows.map((row) => [
  row.spec_id,
  row.project_name,
  row.solution_id,
  row.type,
  row.requirement_title,
  row.content,
  row.control,
  row.acceptance,
  null,
]);
const specialtyLinks = specialRows.map((row) => [
  `=HYPERLINK("${formulaEscape(row.evidence_link)}","打开证据")`,
]);
specialty.getRange(`I${specialStart}:I${specialEnd}`).formulas = specialtyLinks;
body(specialty.getRange(`A${specialStart}:I${specialEnd}`));
specialty.getRange(`I${specialStart}:I${specialEnd}`).format = {
  fill: COLORS.paleBlue,
  font: { name: FONT, size: 10, bold: true, color: "#0563C1", underline: "single" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
specialty.tables.add(`A6:I${specialEnd}`, true, "SpecialtyDesignTable").style = "TableStyleMedium2";
specialty.getRange("A:A").format.columnWidth = 23;
specialty.getRange("B:B").format.columnWidth = 34;
specialty.getRange("C:C").format.columnWidth = 16;
specialty.getRange("D:D").format.columnWidth = 24;
specialty.getRange("E:E").format.columnWidth = 48;
specialty.getRange("F:H").format.columnWidth = 66;
specialty.getRange("I:I").format.columnWidth = 15;
specialty.getRange(`${specialStart}:${specialEnd}`).format.rowHeight = 96;
specialty.freezePanes.freezeRows(6);
specialty.freezePanes.freezeColumns(2);

title(
  guide,
  "使用边界",
  "本包用于内部方案分析和后续交付包准备，不要求用户逐项填写。正式化前必须保留需求、决策、方案和证据的完整 TraceLink。",
  "F",
);
guide.getRange("A6:F6").values = [["对象", "当前状态", "本轮完成", "下一环节", "不能自动完成", "正式化方式"]];
header(guide.getRange("A6:F6"));
guide.getRange("A7:F11").values = [
  ["需求方案映射", "SOLUTION_DRAFT_INTERNAL", "40 条需求与 40 条方案一一对应", "项目级需求与方案交付包", "升级为正式 Solution", "Requirement Review + Solution Review + Gate"],
  ["接口专项", "草案", `${interfaceIds.size} 项`, "冻结 InterfaceSpec", "承诺未验证外部能力", "接口文档、样例和联调证据齐备后冻结"],
  ["迁移专项", "草案", `${migrationIds.size} 项`, "冻结 MigrationSpec", "把试迁移当成正式迁移", "完成盘点、试迁移、校验和回退演练"],
  ["权限专项", "草案", `${permissionIds.size} 项`, "冻结 PermissionDesign", "绕过项目隔离或审计", "完成 Role × Resource × Project 验证"],
  ["外部调用", "本轮未调用", "全部本地确定性处理", "无", "向外部模型发送客户资料", "取得当轮明确数据外发授权"],
];
body(guide.getRange("A7:F11"));
guide.getRange("A7:A11").format.font = { name: FONT, size: 10, bold: true, color: COLORS.blue };
guide.getRange("A:A").format.columnWidth = 24;
guide.getRange("B:B").format.columnWidth = 30;
guide.getRange("C:F").format.columnWidth = 54;
guide.getRange("7:11").format.rowHeight = 68;
guide.getRange("A14:F20").values = [
  ["统计", "数量", "说明", "", "", ""],
  ["项目", projects.length, "第一批项目", "", "", ""],
  ["方案草案", solutions.length, "与需求一一对应", "", "", ""],
  ["标准配置", standardCount, "优先复用标准能力", "", "", ""],
  ["非标实现", customCount, "接口、迁移或领域扩展", "", "", ""],
  ["专项设计", specialRows.length, "接口、迁移和权限专项记录", "", "", ""],
  ["高风险", highRiskCount, "正式方案必须保留控制措施", "", "", ""],
];
guide.getRange("A14:C20").format = {
  font: { name: FONT, size: 10, color: COLORS.text },
  verticalAlignment: "center",
  wrapText: true,
  borders: { bottom: { style: "thin", color: COLORS.border } },
};
guide.getRange("A14:C14").format = {
  fill: COLORS.gray,
  font: { name: FONT, size: 10, bold: true, color: COLORS.blue },
};
guide.getRange("B15:B20").format.horizontalAlignment = "right";
guide.getRange("15:20").format.rowHeight = 32;

workbook.recalculate();
await fs.mkdir(outputDir, { recursive: true });

const linkRanges = [
  { sheet: mapping, address: `P${mappingStart}:P${mappingEnd}`, formulas: mappingLinks, values: solutions.map(() => ["打开证据"]) },
  { sheet: specialty, address: `I${specialStart}:I${specialEnd}`, formulas: specialtyLinks, values: specialRows.map(() => ["打开证据"]) },
];
for (const linkRange of linkRanges) {
  linkRange.sheet.getRange(linkRange.address).values = linkRange.values;
}

const previews = [
  ["方案总览", "A1:K22", "preview-方案总览.png"],
  ["需求方案映射", "A1:R18", "preview-需求方案映射.png"],
  ["专项设计", "A1:I18", "preview-专项设计.png"],
  ["使用边界", "A1:F20", "preview-使用边界.png"],
];
for (const [sheetName, range, fileName] of previews) {
  const preview = await workbook.render({ sheetName, range, scale: 1.05, format: "png" });
  await fs.writeFile(path.join(outputDir, fileName), new Uint8Array(await preview.arrayBuffer()));
}
for (const linkRange of linkRanges) {
  linkRange.sheet.getRange(linkRange.address).formulas = linkRange.formulas;
}
workbook.recalculate();

const outputPath = path.join(outputDir, "第一批项目解决方案草案-R5.xlsx");
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

const saved = await SpreadsheetFile.importXlsx(await FileBlob.load(outputPath));
const validation = [];
for (const [sheetName, range, rows, cols] of [
  ["方案总览", "A1:K22", 22, 11],
  ["需求方案映射", "A1:R18", 18, 18],
  ["专项设计", "A1:I18", 18, 9],
  ["使用边界", "A1:F20", 20, 6],
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
  sheetId: "需求方案映射",
  range: `P${mappingStart}:P${mappingEnd}`,
  maxChars: 16000,
  options: { maxResults: solutions.length },
})).ndjson);
validation.push((await saved.inspect({
  kind: "formula",
  sheetId: "专项设计",
  range: `I${specialStart}:I${specialEnd}`,
  maxChars: 12000,
  options: { maxResults: specialRows.length },
})).ndjson);

await fs.writeFile(path.join(outputDir, "artifact-tool-validation.ndjson"), validation.join("\n"), "utf8");
await fs.writeFile(path.join(outputDir, "workbook-result.json"), JSON.stringify({
  status: payload.status,
  output_path: outputPath,
  project_count: projects.length,
  solution_count: solutions.length,
  standard_count: standardCount,
  custom_count: customCount,
  difference_count: differenceCount,
  working_baseline_count: workingCount,
  interface_count: interfaceIds.size,
  migration_count: migrationIds.size,
  permission_count: permissionIds.size,
  specialty_count: specialRows.length,
  high_risk_count: highRiskCount,
  preview_count: previews.length,
}, null, 2), "utf8");

console.log(JSON.stringify({
  status: payload.status,
  outputPath,
  projectCount: projects.length,
  solutionCount: solutions.length,
  standardCount,
  customCount,
  differenceCount,
  workingBaselineCount: workingCount,
  interfaceCount: interfaceIds.size,
  migrationCount: migrationIds.size,
  permissionCount: permissionIds.size,
  specialtyCount: specialRows.length,
  highRiskCount,
  previewCount: previews.length,
}));
