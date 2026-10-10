import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";


const [payloadPath, outputDir] = process.argv.slice(2);
if (!payloadPath || !outputDir) {
  throw new Error("Usage: node build_implementation_wbs_workbook.mjs <wbs.json> <output-dir>");
}

const payload = JSON.parse(await fs.readFile(payloadPath, "utf8"));
const tasks = payload.tasks;
const projects = payload.projects;
const roles = payload.roles;
const FONT = "Microsoft YaHei";
const COLORS = {
  navy: "#17365D", blue: "#1F4E78", pale: "#DDEBF7", border: "#D9E2F3",
  text: "#1F2937", muted: "#667085", green: "#E2F0D9", amber: "#FFF2CC",
  red: "#FCE4D6", gray: "#F2F2F2", white: "#FFFFFF",
};

const workbook = Workbook.create();
const overview = workbook.worksheets.add("WBS总览");
const taskSheet = workbook.worksheets.add("任务清单");
const dependencySheet = workbook.worksheets.add("依赖与关口");
const roleSheet = workbook.worksheets.add("角色与交付");
const boundarySheet = workbook.worksheets.add("使用边界");
for (const sheet of [overview, taskSheet, dependencySheet, roleSheet, boundarySheet]) {
  sheet.showGridLines = false;
}
overview.tabColor = COLORS.navy;
taskSheet.tabColor = "#70AD47";
dependencySheet.tabColor = "#ED7D31";
roleSheet.tabColor = "#5B9BD5";
boundarySheet.tabColor = "#FFC000";

function title(sheet, heading, context, lastColumn) {
  sheet.getRange(`A2:${lastColumn}2`).format = {
    font: { name: FONT, size: 15, bold: true, color: COLORS.navy },
    verticalAlignment: "center",
  };
  sheet.getRange("A2").values = [[heading]];
  sheet.getRange(`A3:${lastColumn}3`).format = {
    font: { name: FONT, size: 10, italic: true, color: COLORS.muted },
    verticalAlignment: "top", wrapText: true,
    borders: { bottom: { style: "thin", color: COLORS.border } },
  };
  sheet.getRange("A3").values = [[context]];
  sheet.getRange("2:2").format.rowHeight = 26;
  sheet.getRange("3:3").format.rowHeight = 34;
}

function header(range) {
  range.format = {
    fill: COLORS.blue,
    font: { name: FONT, size: 10, bold: true, color: COLORS.white },
    horizontalAlignment: "center", verticalAlignment: "center", wrapText: true,
    borders: { insideVertical: { style: "thin", color: COLORS.white }, bottom: { style: "medium", color: COLORS.navy } },
  };
  range.format.rowHeight = 36;
}

function body(range) {
  range.format = {
    font: { name: FONT, size: 9, color: COLORS.text },
    verticalAlignment: "top", wrapText: true,
    borders: { bottom: { style: "thin", color: COLORS.border } },
  };
}

function formulaEscape(value) {
  return String(value || "").replaceAll('"', '""');
}

title(overview, "PLM 项目实施 WBS 草案", "基于 R6 内部需求与解决方案交付包生成；仅用于内部实施准备，不包含人员姓名、承诺日期或正式工期。", "N");
overview.getRange("A5:N5").values = [[
  "版本", payload.version, "项目", payload.summary.project_count, "任务", payload.summary.task_count,
  "需求交付任务", payload.summary.requirement_delivery_task_count, "项目控制任务", payload.summary.project_control_task_count,
  "正式状态", payload.formal_status, "排期状态", "未排期",
]];
overview.getRange("A5:N5").format = { fill: COLORS.gray, font: { name: FONT, size: 10, color: COLORS.text }, verticalAlignment: "center", borders: { preset: "outside", style: "thin", color: COLORS.border } };
for (const col of ["A", "C", "E", "G", "I", "K", "M"]) overview.getRange(`${col}5`).format.font = { name: FONT, size: 10, bold: true, color: COLORS.blue };
for (const col of ["B", "D", "F", "H", "J", "L", "N"]) overview.getRange(`${col}5`).format.font = { name: FONT, size: 11, bold: true, color: COLORS.navy };

overview.getRange("A8:N8").values = [["项目", "任务", "需求任务", "控制任务", "W0", "W1", "W2", "W3", "W4", "P0", "高风险", "当前状态", "正式化状态", "下一步"]];
header(overview.getRange("A8:N8"));
const pStart = 9;
const pEnd = pStart + projects.length - 1;
overview.getRange(`A${pStart}:N${pEnd}`).values = projects.map((project) => {
  const pt = tasks.filter((task) => task.project_id === project.project_id);
  const wc = (wave) => pt.filter((task) => task.wave === wave).length;
  return [project.project_name, project.wbs_task_count, project.requirement_delivery_task_count, project.project_control_task_count,
    wc("W0"), wc("W1"), wc("W2"), wc("W3"), wc("W4"), pt.filter((task) => task.priority === "P0").length,
    pt.filter((task) => task.risk === "高").length, project.planning_status, project.formal_readiness, project.recommended_next];
});
body(overview.getRange(`A${pStart}:N${pEnd}`));
overview.tables.add(`A8:N${pEnd}`, true, "WbsProjectSummaryTable").style = "TableStyleMedium4";
overview.getRange("A:A").format.columnWidth = 34;
overview.getRange("B:K").format.columnWidth = 12;
overview.getRange("L:M").format.columnWidth = 27;
overview.getRange("N:N").format.columnWidth = 58;
overview.getRange(`${pStart}:${pEnd}`).format.rowHeight = 66;

overview.getRange("A17:F17").values = [["批次", "批次名称", "任务数", "进入条件", "主要输出", "关口"]];
header(overview.getRange("A17:F17"));
const waveRows = payload.waves.map((wave) => {
  const waveTasks = tasks.filter((task) => task.wave === wave.code);
  const sample = waveTasks[0];
  return [wave.code, wave.name, waveTasks.length, sample?.entry_condition || "", sample?.work_output || "", sample?.gate || ""];
});
overview.getRange("A18:F22").values = waveRows;
body(overview.getRange("A18:F22"));
overview.getRange("A:A").format.columnWidth = 16;
overview.getRange("B:B").format.columnWidth = 27;
overview.getRange("C:C").format.columnWidth = 12;
overview.getRange("D:F").format.columnWidth = 54;
overview.getRange("18:22").format.rowHeight = 62;
overview.freezePanes.freezeRows(8);
overview.freezePanes.freezeColumns(1);

title(taskSheet, "实施任务清单", "60 条任务均为内部草案；40 条需求交付任务保留需求、方案、交付与证据链接，20 条为项目治理、联调、验收和交接任务。", "V");
taskSheet.getRange("A6:V6").values = [[
  "任务编号", "项目", "批次", "任务类型", "任务名称", "类别", "优先级", "风险", "主责角色", "协作角色",
  "前置任务", "进入条件", "工作输出", "验收标准", "完成证据", "明确排除", "需求编号", "方案编号", "交付编号", "专项类型", "打开证据", "状态",
]];
header(taskSheet.getRange("A6:V6"));
const tStart = 7;
const tEnd = tStart + tasks.length - 1;
taskSheet.getRange(`A${tStart}:V${tEnd}`).values = tasks.map((task) => [
  task.task_id, task.project_name, `${task.wave} ${task.wave_name}`, task.task_type, task.task_name, task.category, task.priority, task.risk,
  task.owner_role, task.support_roles, task.predecessors.join("；"), task.entry_condition, task.work_output, task.acceptance, task.evidence,
  task.explicit_exclusion, task.requirement_id, task.solution_id, task.delivery_id, task.specialty_types.join("；"), task.trace_link ? "打开证据" : "", task.status,
]);
const taskLinks = tasks.map((task) => [task.trace_link ? `=HYPERLINK("${formulaEscape(task.trace_link)}","打开证据")` : ""]);
body(taskSheet.getRange(`A${tStart}:V${tEnd}`));
taskSheet.getRange(`U${tStart}:U${tEnd}`).format = { fill: COLORS.pale, font: { name: FONT, size: 9, bold: true, color: "#0563C1", underline: "single" }, horizontalAlignment: "center", verticalAlignment: "center" };
taskSheet.getRange(`G${tStart}:G${tEnd}`).conditionalFormats.addCustom(`=G${tStart}="P0"`, { fill: COLORS.red, font: { bold: true, color: "#9C0006" } });
taskSheet.getRange(`H${tStart}:H${tEnd}`).conditionalFormats.addCustom(`=H${tStart}="高"`, { fill: COLORS.red, font: { bold: true, color: "#9C0006" } });
taskSheet.tables.add(`A6:V${tEnd}`, true, "ImplementationWbsTaskTable").style = "TableStyleMedium4";
taskSheet.getRange("A:A").format.columnWidth = 18;
taskSheet.getRange("B:B").format.columnWidth = 34;
taskSheet.getRange("C:D").format.columnWidth = 23;
taskSheet.getRange("E:F").format.columnWidth = 44;
taskSheet.getRange("G:H").format.columnWidth = 12;
taskSheet.getRange("I:J").format.columnWidth = 24;
taskSheet.getRange("K:K").format.columnWidth = 38;
taskSheet.getRange("L:P").format.columnWidth = 58;
taskSheet.getRange("Q:T").format.columnWidth = 20;
taskSheet.getRange("U:V").format.columnWidth = 22;
taskSheet.getRange(`${tStart}:${tEnd}`).format.rowHeight = 104;
taskSheet.freezePanes.freezeRows(6);
taskSheet.freezePanes.freezeColumns(5);

title(dependencySheet, "依赖与 Gate", "每项前置任务都引用同一工作簿内的任务编号；正式排期前需在资源、环境和 Gate 条件明确后补充日历计划。", "J");
dependencySheet.getRange("A6:J6").values = [["任务编号", "项目", "批次", "任务名称", "前置任务", "关口", "进入条件", "验收标准", "风险", "状态"]];
header(dependencySheet.getRange("A6:J6"));
dependencySheet.getRange(`A${tStart}:J${tEnd}`).values = tasks.map((task) => [task.task_id, task.project_name, task.wave, task.task_name, task.predecessors.join("；"), task.gate, task.entry_condition, task.acceptance, task.risk, task.status]);
body(dependencySheet.getRange(`A${tStart}:J${tEnd}`));
dependencySheet.tables.add(`A6:J${tEnd}`, true, "WbsDependencyGateTable").style = "TableStyleMedium9";
dependencySheet.getRange("A:A").format.columnWidth = 18;
dependencySheet.getRange("B:B").format.columnWidth = 34;
dependencySheet.getRange("C:C").format.columnWidth = 12;
dependencySheet.getRange("D:D").format.columnWidth = 44;
dependencySheet.getRange("E:J").format.columnWidth = 48;
dependencySheet.getRange(`${tStart}:${tEnd}`).format.rowHeight = 86;
dependencySheet.freezePanes.freezeRows(6);
dependencySheet.freezePanes.freezeColumns(2);

title(roleSheet, "角色与交付", "只定义角色，不指定人员；正式项目计划需由管理层确认资源和责任人后再映射。", "F");
roleSheet.getRange("A6:F6").values = [["角色", "主要责任", "主责任务数", "协作任务数", "关键 Gate", "排期说明"]];
header(roleSheet.getRange("A6:F6"));
const rStart = 7;
const rEnd = rStart + roles.length - 1;
roleSheet.getRange(`A${rStart}:F${rEnd}`).values = roles.map((role) => [
  role.role, role.responsibility, tasks.filter((task) => task.owner_role === role.role).length,
  tasks.filter((task) => String(task.support_roles).includes(role.role)).length,
  [...new Set(tasks.filter((task) => task.owner_role === role.role).map((task) => task.gate))].join("；"),
  "待资源确认后补充责任人和日历计划",
]);
body(roleSheet.getRange(`A${rStart}:F${rEnd}`));
roleSheet.tables.add(`A6:F${rEnd}`, true, "WbsRoleTable").style = "TableStyleMedium2";
roleSheet.getRange("A:A").format.columnWidth = 24;
roleSheet.getRange("B:B").format.columnWidth = 54;
roleSheet.getRange("C:D").format.columnWidth = 16;
roleSheet.getRange("E:F").format.columnWidth = 52;
roleSheet.getRange(`${rStart}:${rEnd}`).format.rowHeight = 70;
roleSheet.freezePanes.freezeRows(6);

title(boundarySheet, "使用边界与维护说明", "本页必须与 WBS 一同交付，防止草案被误读为正式承诺。", "F");
boundarySheet.getRange("A6:F6").values = [["编号", "边界/规则", "原因", "触发动作", "责任角色", "正式状态"]];
header(boundarySheet.getRange("A6:F6"));
const boundaries = payload.boundaries.map((text, index) => [
  `B-${String(index + 1).padStart(2, "0")}`, text,
  index === 0 ? "防止内部工作稿成为合同或正式基线" : index === 1 ? "遵守仓库 Gate 与冻结顺序" : index === 2 ? "避免虚构资源与计划承诺" : "保证审计与可追溯",
  index === 1 ? "Phase/Gate 满足后另行发布正式 WBS" : "正式评审时逐项确认并升版",
  index === 2 ? "项目负责人/管理层" : "项目负责人",
  payload.formal_status,
]);
boundarySheet.getRange(`A7:F${6 + boundaries.length}`).values = boundaries;
body(boundarySheet.getRange(`A7:F${6 + boundaries.length}`));
boundarySheet.getRange("A:A").format.columnWidth = 14;
boundarySheet.getRange("B:D").format.columnWidth = 68;
boundarySheet.getRange("E:F").format.columnWidth = 28;
boundarySheet.getRange(`7:${6 + boundaries.length}`).format.rowHeight = 82;
boundarySheet.getRange("A14:F14").values = [["维护项", "需要维护的信息", "维护时点", "校验要求", "责任角色", "备注"]];
header(boundarySheet.getRange("A14:F14"));
boundarySheet.getRange("A15:F19").values = [
  ["责任人", "把角色映射为实名责任人", "资源确认后", "每项任务必须唯一主责", "项目负责人", "不得由 AI 猜测姓名"],
  ["日历计划", "开始/结束日期、工期、里程碑", "Gate 通过并确认资源后", "依赖关系无断链", "项目负责人", "当前版本刻意留空"],
  ["环境", "开发/测试/生产环境可用性", "进入对应任务前", "有检查记录与异常闭环", "集成工程师", "缺失则任务不得开工"],
  ["验收人", "业务/技术验收责任人", "验收准备前", "与需求和用例一一对应", "测试负责人", "不得只写部门"],
  ["版本", "正式需求、方案、接口与数据模型版本", "每次 Gate 后", "TraceLink 可反向追溯", "项目负责人", "保留历史版本"],
];
body(boundarySheet.getRange("A15:F19"));
boundarySheet.getRange("15:19").format.rowHeight = 66;

workbook.recalculate();
await fs.mkdir(outputDir, { recursive: true });
const previews = [
  ["WBS总览", "A1:N22", "preview-WBS总览.png"],
  ["任务清单", "A1:V18", "preview-任务清单.png"],
  ["依赖与关口", "A1:J18", "preview-依赖与关口.png"],
  ["角色与交付", "A1:F15", "preview-角色与交付.png"],
  ["使用边界", "A1:F19", "preview-使用边界.png"],
];
for (const [sheetName, range, fileName] of previews) {
  const preview = await workbook.render({ sheetName, range, scale: 1.0, format: "png" });
  await fs.writeFile(path.join(outputDir, fileName), new Uint8Array(await preview.arrayBuffer()));
}
taskSheet.getRange(`U${tStart}:U${tEnd}`).formulas = taskLinks;
workbook.recalculate();
const outputPath = path.join(outputDir, "PLM项目实施WBS草案-R7.xlsx");
await (await SpreadsheetFile.exportXlsx(workbook)).save(outputPath);

const saved = await SpreadsheetFile.importXlsx(await FileBlob.load(outputPath));
const validation = [];
for (const [sheetName, range, rows, cols] of [
  ["WBS总览", "A1:N22", 22, 14], ["任务清单", "A1:V18", 18, 22],
  ["依赖与关口", "A1:J18", 18, 10], ["角色与交付", "A1:F15", 15, 6], ["使用边界", "A1:F19", 19, 6],
]) {
  validation.push((await saved.inspect({ kind: "table", range: `${sheetName}!${range}`, include: "values,formulas", tableMaxRows: rows, tableMaxCols: cols, maxChars: 32000 })).ndjson);
}
validation.push((await saved.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: { useRegex: true, maxResults: 300 }, maxChars: 12000 })).ndjson);
validation.push((await saved.inspect({ kind: "formula", sheetId: "任务清单", range: `U${tStart}:U${tEnd}`, maxChars: 30000, options: { maxResults: tasks.length } })).ndjson);
await fs.writeFile(path.join(outputDir, "artifact-tool-validation.ndjson"), validation.join("\n"), "utf8");
await fs.writeFile(path.join(outputDir, "workbook-result.json"), JSON.stringify({ status: payload.status, formal_status: payload.formal_status, output_path: outputPath, project_count: projects.length, task_count: tasks.length, trace_link_count: tasks.filter((task) => task.trace_link).length, preview_count: previews.length }, null, 2), "utf8");
console.log(JSON.stringify({ outputPath, projectCount: projects.length, taskCount: tasks.length, traceLinkCount: tasks.filter((task) => task.trace_link).length, previewCount: previews.length }));
