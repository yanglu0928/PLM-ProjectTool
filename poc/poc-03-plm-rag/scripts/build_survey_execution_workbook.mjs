import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";


const [packagePath, outputDir] = process.argv.slice(2);
if (!packagePath || !outputDir) {
  throw new Error("Usage: node build_survey_execution_workbook.mjs <package.json> <output-dir>");
}

const payload = JSON.parse(await fs.readFile(packagePath, "utf8"));
const projects = payload.projects;
const tasks = payload.tasks;
const decisions = payload.decisions;

const FONT = "Arial";
const COLORS = {
  navy: "#17365D",
  blue: "#1F4E78",
  midBlue: "#5B9BD5",
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
const dashboard = workbook.worksheets.add("执行看板");
const taskSheet = workbook.worksheets.add("调研任务");
const decisionSheet = workbook.worksheets.add("决策追踪");
const guide = workbook.worksheets.add("使用说明");

dashboard.tabColor = COLORS.navy;
taskSheet.tabColor = COLORS.blue;
decisionSheet.tabColor = "#ED7D31";
guide.tabColor = "#A5A5A5";
for (const sheet of [dashboard, taskSheet, decisionSheet, guide]) {
  sheet.showGridLines = false;
}

function styleTitle(sheet, title, context, lastColumn) {
  sheet.getRange(`A2:${lastColumn}2`).format = {
    font: { name: FONT, size: 14, bold: true, color: COLORS.navy },
    verticalAlignment: "center",
  };
  sheet.getRange("A2").values = [[title]];
  sheet.getRange(`A3:${lastColumn}3`).format = {
    font: { name: FONT, size: 10, italic: true, color: COLORS.muted },
    verticalAlignment: "top",
    wrapText: false,
    borders: { bottom: { style: "thin", color: COLORS.border } },
  };
  sheet.getRange("A3").values = [[context]];
  sheet.getRange("A3").format.wrapText = false;
  sheet.getRange("2:2").format.rowHeight = 24;
  sheet.getRange("3:3").format.rowHeight = 20;
}

function styleHeader(range) {
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

function styleBody(range) {
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

styleTitle(
  dashboard,
  "PLM 项目调研执行清单",
  payload.scope_note,
  "O",
);
dashboard.getRange("A5:N5").format = {
  fill: COLORS.gray,
  font: { name: FONT, size: 10, color: COLORS.text },
  verticalAlignment: "center",
  borders: { preset: "outside", style: "thin", color: COLORS.border },
};
dashboard.getRange("A5:N5").values = [[
  "项目数", null, "", "调研任务", null, "", "P0 任务", null, "", "未安排任务", null, "", "待决策", null,
]];
dashboard.getRange("B5").formulas = [[`=COUNTA(B9:B${8 + projects.length})`]];
dashboard.getRange("E5").formulas = [[`=COUNTA('调研任务'!$A$7:$A$${6 + tasks.length})`]];
dashboard.getRange("H5").formulas = [[`=COUNTIF('调研任务'!$E$7:$E$${6 + tasks.length},"P0")`]];
dashboard.getRange("K5").formulas = [[`=COUNTIF('调研任务'!$Q$7:$Q$${6 + tasks.length},"未安排")`]];
dashboard.getRange("N5").formulas = [[`=COUNTIF('决策追踪'!$J$7:$J$${6 + decisions.length},"待决策")`]];
for (const cell of ["A5", "D5", "G5", "J5", "M5"]) {
  dashboard.getRange(cell).format.font = { name: FONT, size: 10, bold: true, color: COLORS.blue };
}
for (const cell of ["B5", "E5", "H5", "K5", "N5"]) {
  dashboard.getRange(cell).format.font = { name: FONT, size: 12, bold: true, color: COLORS.navy };
  dashboard.getRange(cell).format.horizontalAlignment = "center";
  dashboard.getRange(cell).format.numberFormat = "#,##0";
}

dashboard.getRange("A8:O8").values = [[
  "顺序", "项目", "批次", "资料成熟度", "资料数", "任务数", "P0 任务", "待决策", "首要动作", "项目负责人", "计划开始", "计划完成", "项目状态", "已完成任务", "备注",
]];
styleHeader(dashboard.getRange("A8:O8"));
const projectStart = 9;
const projectEnd = projectStart + projects.length - 1;
dashboard.getRange(`A${projectStart}:O${projectEnd}`).values = projects.map((project) => [
  project.recommended_order,
  project.project_name,
  `第${project.wave}批`,
  project.source_maturity,
  project.source_count,
  project.task_count,
  project.p0_count,
  project.pending_decision_count,
  project.first_action,
  project.owner,
  project.planned_start,
  project.planned_end,
  project.status,
  null,
  project.notes,
]);
styleBody(dashboard.getRange(`A${projectStart}:O${projectEnd}`));
dashboard.getRange(`J${projectStart}:M${projectEnd}`).format.fill = COLORS.amber;
dashboard.getRange(`O${projectStart}:O${projectEnd}`).format.fill = COLORS.amber;
dashboard.getRange(`K${projectStart}:L${projectEnd}`).format.numberFormat = "yyyy-mm-dd";
dashboard.getRange(`M${projectStart}:M${projectEnd}`).dataValidation = {
  rule: { type: "list", values: ["未安排", "已排期", "进行中", "已完成", "阻塞"] },
};
for (let row = projectStart; row <= projectEnd; row += 1) {
  dashboard.getRange(`N${row}`).formulas = [[
    `=COUNTIFS('调研任务'!$C$7:$C$${6 + tasks.length},B${row},'调研任务'!$Q$7:$Q$${6 + tasks.length},"已完成")&"/"&F${row}`,
  ]];
}
dashboard.getRange(`M${projectStart}:M${projectEnd}`).conditionalFormats.addCustom(
  `=M${projectStart}="已完成"`,
  { fill: COLORS.green, font: { bold: true, color: COLORS.greenText } },
);
dashboard.getRange(`M${projectStart}:M${projectEnd}`).conditionalFormats.addCustom(
  `=M${projectStart}="阻塞"`,
  { fill: COLORS.red, font: { bold: true, color: COLORS.redText } },
);
dashboard.getRange("A:A").format.columnWidth = 8;
dashboard.getRange("B:B").format.columnWidth = 34;
dashboard.getRange("C:C").format.columnWidth = 10;
dashboard.getRange("D:D").format.columnWidth = 29;
dashboard.getRange("E:H").format.columnWidth = 11;
dashboard.getRange("I:I").format.columnWidth = 52;
dashboard.getRange("J:J").format.columnWidth = 18;
dashboard.getRange("K:L").format.columnWidth = 14;
dashboard.getRange("M:N").format.columnWidth = 15;
dashboard.getRange("O:O").format.columnWidth = 40;
dashboard.getRange(`${projectStart}:${projectEnd}`).format.rowHeight = 62;
dashboard.freezePanes.freezeRows(8);
dashboard.freezePanes.freezeColumns(2);

styleTitle(
  taskSheet,
  "调研任务",
  "按执行看板中的推荐顺序开展。黄色列由项目团队维护；点击“打开证据”查看 R1 分析依据和原文定位。完成任务时，应提交预期产出，并把仍未解决的问题登记到“决策追踪”。",
  "R",
);
taskSheet.getRange("A6:R6").values = [[
  "任务编号", "项目顺序", "项目", "批次", "优先级", "调研主题", "为什么要做", "建议参与人", "会前资料", "核心问题", "预期产出", "完成标准", "关联分析", "打开证据", "负责人", "计划日期", "状态", "记录/备注",
]];
styleHeader(taskSheet.getRange("A6:R6"));
const taskStart = 7;
const taskEnd = taskStart + tasks.length - 1;
const projectOrder = new Map(projects.map((project) => [project.project_id, project.recommended_order]));
taskSheet.getRange(`A${taskStart}:R${taskEnd}`).values = tasks.map((task) => [
  task.task_id,
  projectOrder.get(task.project_id),
  task.project_name,
  `第${task.wave}批`,
  task.priority,
  task.topic,
  task.reason,
  task.participants,
  task.required_materials,
  task.questions,
  task.expected_output,
  task.acceptance_criteria,
  task.related_item_ids.join("、"),
  null,
  task.owner,
  task.planned_date,
  task.status,
  task.notes,
]);
const taskLinkFormulas = tasks.map((task) => [
  `=HYPERLINK("${formulaEscape(task.evidence_link)}","打开证据")`,
]);
taskSheet.getRange(`N${taskStart}:N${taskEnd}`).formulas = taskLinkFormulas;
styleBody(taskSheet.getRange(`A${taskStart}:R${taskEnd}`));
taskSheet.getRange(`N${taskStart}:N${taskEnd}`).format = {
  fill: COLORS.paleBlue,
  font: { name: FONT, size: 10, bold: true, color: "#0563C1", underline: "single" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
taskSheet.getRange(`O${taskStart}:R${taskEnd}`).format.fill = COLORS.amber;
taskSheet.getRange(`P${taskStart}:P${taskEnd}`).format.numberFormat = "yyyy-mm-dd";
taskSheet.getRange(`Q${taskStart}:Q${taskEnd}`).dataValidation = {
  rule: { type: "list", values: ["未安排", "已排期", "进行中", "已完成", "阻塞"] },
};
taskSheet.getRange(`E${taskStart}:E${taskEnd}`).conditionalFormats.addCustom(
  `=E${taskStart}="P0"`,
  { fill: COLORS.red, font: { bold: true, color: COLORS.redText } },
);
taskSheet.getRange(`Q${taskStart}:Q${taskEnd}`).conditionalFormats.addCustom(
  `=Q${taskStart}="已完成"`,
  { fill: COLORS.green, font: { bold: true, color: COLORS.greenText } },
);
taskSheet.getRange(`Q${taskStart}:Q${taskEnd}`).conditionalFormats.addCustom(
  `=Q${taskStart}="阻塞"`,
  { fill: COLORS.red, font: { bold: true, color: COLORS.redText } },
);
taskSheet.tables.add(`A6:R${taskEnd}`, true, "SurveyTasksTable").style = "TableStyleMedium2";
taskSheet.getRange(`O${taskStart}:R${taskEnd}`).format.fill = COLORS.amber;
taskSheet.getRange("A:A").format.columnWidth = 13;
taskSheet.getRange("B:B").format.columnWidth = 10;
taskSheet.getRange("C:C").format.columnWidth = 34;
taskSheet.getRange("D:E").format.columnWidth = 11;
taskSheet.getRange("F:F").format.columnWidth = 26;
taskSheet.getRange("G:G").format.columnWidth = 40;
taskSheet.getRange("H:H").format.columnWidth = 36;
taskSheet.getRange("I:I").format.columnWidth = 56;
taskSheet.getRange("J:J").format.columnWidth = 60;
taskSheet.getRange("K:K").format.columnWidth = 34;
taskSheet.getRange("L:L").format.columnWidth = 56;
taskSheet.getRange("M:N").format.columnWidth = 16;
taskSheet.getRange("O:O").format.columnWidth = 18;
taskSheet.getRange("P:Q").format.columnWidth = 14;
taskSheet.getRange("R:R").format.columnWidth = 44;
taskSheet.getRange(`${taskStart}:${taskEnd}`).format.rowHeight = 84;
taskSheet.freezePanes.freezeRows(6);
taskSheet.freezePanes.freezeColumns(3);

styleTitle(
  decisionSheet,
  "决策追踪",
  "本页已把 R1 的 24 条待确认项转为决策记录。黄色列由项目团队维护；只有状态为“已决策”且填写最终决策后，相关内容才可进入正式需求或方案。",
  "L",
);
decisionSheet.getRange("A6:L6").values = [[
  "决策编号", "项目", "待决策事项", "为什么未决", "建议处理", "打开证据", "责任人", "截止日期", "最终决策", "状态", "影响范围", "记录/备注",
]];
styleHeader(decisionSheet.getRange("A6:L6"));
const decisionStart = 7;
const decisionEnd = decisionStart + decisions.length - 1;
decisionSheet.getRange(`A${decisionStart}:L${decisionEnd}`).values = decisions.map((item) => [
  item.decision_id,
  item.project_name,
  item.topic,
  item.question,
  item.recommendation,
  null,
  item.owner,
  item.due_date,
  item.decision,
  item.status,
  "",
  item.notes,
]);
const decisionLinkFormulas = decisions.map((item) => [
  `=HYPERLINK("${formulaEscape(item.evidence_link)}","打开证据")`,
]);
decisionSheet.getRange(`F${decisionStart}:F${decisionEnd}`).formulas = decisionLinkFormulas;
styleBody(decisionSheet.getRange(`A${decisionStart}:L${decisionEnd}`));
decisionSheet.getRange(`F${decisionStart}:F${decisionEnd}`).format = {
  fill: COLORS.paleBlue,
  font: { name: FONT, size: 10, bold: true, color: "#0563C1", underline: "single" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
decisionSheet.getRange(`G${decisionStart}:L${decisionEnd}`).format.fill = COLORS.amber;
decisionSheet.getRange(`H${decisionStart}:H${decisionEnd}`).format.numberFormat = "yyyy-mm-dd";
decisionSheet.getRange(`J${decisionStart}:J${decisionEnd}`).dataValidation = {
  rule: { type: "list", values: ["待决策", "讨论中", "已决策", "暂缓"] },
};
decisionSheet.getRange(`J${decisionStart}:J${decisionEnd}`).conditionalFormats.addCustom(
  `=J${decisionStart}="已决策"`,
  { fill: COLORS.green, font: { bold: true, color: COLORS.greenText } },
);
decisionSheet.getRange(`J${decisionStart}:J${decisionEnd}`).conditionalFormats.addCustom(
  `=J${decisionStart}="待决策"`,
  { fill: COLORS.red, font: { bold: true, color: COLORS.redText } },
);
decisionSheet.tables.add(`A6:L${decisionEnd}`, true, "SurveyDecisionsTable").style = "TableStyleMedium2";
decisionSheet.getRange(`G${decisionStart}:L${decisionEnd}`).format.fill = COLORS.amber;
decisionSheet.getRange("A:A").format.columnWidth = 17;
decisionSheet.getRange("B:B").format.columnWidth = 34;
decisionSheet.getRange("C:C").format.columnWidth = 46;
decisionSheet.getRange("D:E").format.columnWidth = 56;
decisionSheet.getRange("F:F").format.columnWidth = 15;
decisionSheet.getRange("G:G").format.columnWidth = 18;
decisionSheet.getRange("H:H").format.columnWidth = 14;
decisionSheet.getRange("I:I").format.columnWidth = 48;
decisionSheet.getRange("J:J").format.columnWidth = 14;
decisionSheet.getRange("K:L").format.columnWidth = 36;
decisionSheet.getRange(`${decisionStart}:${decisionEnd}`).format.rowHeight = 84;
decisionSheet.freezePanes.freezeRows(6);
decisionSheet.freezePanes.freezeColumns(2);

styleTitle(
  guide,
  "使用说明",
  "先安排项目，再执行调研任务，最后关闭决策项。表中所有黄色单元格都需要项目团队维护；蓝色“打开证据”用于返回 R1 分析依据。",
  "F",
);
guide.getRange("A6:F6").values = [["步骤", "在哪维护", "需要填写", "完成条件", "注意事项", "结果去向"]];
styleHeader(guide.getRange("A6:F6"));
guide.getRange("A7:F10").values = [
  ["1. 安排项目", "执行看板", "负责人、计划开始/完成、项目状态", "项目进入“已排期”或“进行中”", "第3/4批项目先补真实业务调研，不直接按方案定需求", "形成项目级调研日程"],
  ["2. 执行调研", "调研任务", "负责人、计划日期、状态、记录/备注", "提交预期产出，未决问题已登记", "会前资料必须准备；业务表单只能作提问参考", "形成范围、流程、接口、数据和验收材料"],
  ["3. 关闭决策", "决策追踪", "责任人、截止日期、最终决策、状态、影响范围", "状态为“已决策”且最终决策非空", "口头结论要留痕；新事实仍需可追溯", "经确认后进入正式需求/方案候选"],
  ["4. 查看证据", "调研任务/决策追踪", "点击“打开证据”", "能定位 R1 分析条目和本地原文", "证据链接均为本地；本轮未调用外部模型", "支持复核和追溯"],
];
styleBody(guide.getRange("A7:F10"));
guide.getRange("A7:A10").format.font = { name: FONT, size: 10, bold: true, color: COLORS.blue };
guide.getRange("A:A").format.columnWidth = 18;
guide.getRange("B:B").format.columnWidth = 24;
guide.getRange("C:F").format.columnWidth = 48;
guide.getRange("7:10").format.rowHeight = 70;
guide.getRange("A13:F17").values = [
  ["优先级", "含义", "使用方式", "", "", ""],
  ["P0", "会阻塞范围、接口、数据、安全、合同或验收边界", "优先排期；未完成前不冻结相关方案", "", "", ""],
  ["P1", "用于完善业务流程、对象模型和实施细节", "在 P0 之后或可并行时执行", "", "", ""],
  ["第1/2批", "已有真实调研或较完整约束资料", "以核实差异和补齐缺口为主", "", "", ""],
  ["第3/4批", "缺少真实调研或仅有方案资料", "先确认项目状态、现状主线和正式范围", "", "", ""],
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
guide.getRange("A14:A14").format = { fill: COLORS.red, font: { name: FONT, size: 10, bold: true, color: COLORS.redText } };
guide.getRange("A15:A15").format = { fill: COLORS.amber, font: { name: FONT, size: 10, bold: true, color: COLORS.amberText } };
guide.getRange("14:17").format.rowHeight = 38;

workbook.recalculate();
await fs.mkdir(outputDir, { recursive: true });

const linkRanges = [
  {
    sheet: taskSheet,
    address: `N${taskStart}:N${taskEnd}`,
    formulas: taskLinkFormulas,
    values: tasks.map(() => ["打开证据"]),
  },
  {
    sheet: decisionSheet,
    address: `F${decisionStart}:F${decisionEnd}`,
    formulas: decisionLinkFormulas,
    values: decisions.map(() => ["打开证据"]),
  },
];
for (const linkRange of linkRanges) {
  linkRange.sheet.getRange(linkRange.address).values = linkRange.values;
}

const previews = [
  ["执行看板", `A1:O${projectEnd}`, "preview-执行看板.png"],
  ["调研任务", "A1:R18", "preview-调研任务.png"],
  ["决策追踪", "A1:L18", "preview-决策追踪.png"],
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

const outputPath = path.join(outputDir, "PLM项目调研执行清单-R2.xlsx");
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

const saved = await SpreadsheetFile.importXlsx(await FileBlob.load(outputPath));
const validation = [];
for (const [sheetName, range, rows, cols] of [
  ["执行看板", `A1:O${projectEnd}`, projectEnd, 15],
  ["调研任务", "A1:R18", 18, 18],
  ["决策追踪", "A1:L18", 18, 12],
  ["使用说明", "A1:F17", 17, 6],
]) {
  const inspected = await saved.inspect({
    kind: "table",
    range: `${sheetName}!${range}`,
    include: "values,formulas",
    tableMaxRows: rows,
    tableMaxCols: cols,
    maxChars: 26000,
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

const before = await saved.inspect({
  kind: "table",
  range: "执行看板!A5:N5",
  include: "values,formulas",
  tableMaxRows: 1,
  tableMaxCols: 14,
  maxChars: 5000,
});
validation.push(before.ndjson);
saved.worksheets.getItem("调研任务").getRange("Q7").values = [["已完成"]];
saved.worksheets.getItem("决策追踪").getRange("I7:J7").values = [["采用建议方案", "已决策"]];
saved.recalculate();
const after = await saved.inspect({
  kind: "table",
  range: "执行看板!A5:N9",
  include: "values,formulas",
  tableMaxRows: 5,
  tableMaxCols: 14,
  maxChars: 9000,
});
validation.push(after.ndjson);

await fs.writeFile(path.join(outputDir, "artifact-tool-validation.ndjson"), validation.join("\n"), "utf8");
await fs.writeFile(path.join(outputDir, "workbook-result.json"), JSON.stringify({
  status: payload.status,
  output_path: outputPath,
  project_count: projects.length,
  task_count: tasks.length,
  p0_count: tasks.filter((task) => task.priority === "P0").length,
  decision_count: decisions.length,
  preview_count: previews.length,
}, null, 2), "utf8");

console.log(JSON.stringify({
  status: payload.status,
  outputPath,
  projectCount: projects.length,
  taskCount: tasks.length,
  p0Count: tasks.filter((task) => task.priority === "P0").length,
  decisionCount: decisions.length,
  previewCount: previews.length,
}));
