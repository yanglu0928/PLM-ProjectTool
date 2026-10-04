import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [r4WorkbookPath, goldenPath, qualityPath, outputDir] = process.argv.slice(2);
if (!r4WorkbookPath || !goldenPath || !qualityPath || !outputDir) {
  throw new Error(
    "usage: build_r5_label_review.mjs <r4.xlsx> <golden.json> <case-level.json> <output-dir>",
  );
}

const CLASSIFICATIONS = {
  STANDARD_SATISFIED: "标准满足",
  PARTIALLY_SATISFIED: "部分满足",
  NON_STANDARD: "非标准",
  INSUFFICIENT_INFORMATION: "资料不足",
  NO_RELIABLE_MATCH: "无可靠匹配",
  HUMAN_CONFIRMATION_REQUIRED: "需人工确认",
};
const CLASSIFICATION_NAMES = Object.values(CLASSIFICATIONS);
const NAME_TO_CODE = Object.fromEntries(
  Object.entries(CLASSIFICATIONS).map(([code, name]) => [name, code]),
);
const FONT = "Arial";
const COLORS = {
  navy: "#17365D",
  blue: "#D9EAF7",
  paleBlue: "#EAF3F8",
  amber: "#FFF2CC",
  amberStrong: "#FFD966",
  green: "#E2F0D9",
  red: "#FCE4D6",
  redText: "#9C0006",
  gray: "#F2F2F2",
  border: "#B4C6E7",
  text: "#1F1F1F",
};

function parseExplicitClassification(note) {
  const text = String(note || "");
  const noReliableMarkers = [
    "暂不作为独立需求项",
    "无法形成有效合同结论",
    "更像缩写、编号或OCR片段",
  ];
  if (noReliableMarkers.some((marker) => text.includes(marker))) {
    return "NO_RELIABLE_MATCH";
  }
  for (const [code, name] of Object.entries(CLASSIFICATIONS)) {
    if (
      text.includes(`“${name}”`) ||
      text.includes(`按“${name}”`) ||
      text.includes(`按${name}处理`)
    ) {
      return code;
    }
  }
  const insufficientMarkers = [
    "证据片段不足",
    "摘录不足",
    "不足以完整判断",
    "单凭该片段无法",
    "尚不能",
  ];
  if (insufficientMarkers.some((marker) => text.includes(marker))) {
    return "INSUFFICIENT_INFORMATION";
  }
  return null;
}

function documentKey(chunkId) {
  return String(chunkId).split("-C-")[0];
}

function configureSheet(sheet, tabColor) {
  sheet.showGridLines = false;
  sheet.tabColor = tabColor;
}

function styleTitle(sheet, title, subtitle, width) {
  sheet.getRange(`A2:${width}2`).format.borders = {
    bottom: { style: "thin", color: COLORS.navy },
  };
  sheet.getRange("A2").values = [[title]];
  sheet.getRange("A2").format.font = {
    name: FONT,
    size: 14,
    bold: true,
    color: COLORS.navy,
  };
  sheet.getRange(`A3:${width}3`).merge();
  sheet.getRange("A3").values = [[subtitle]];
  sheet.getRange("A3").format = {
    font: { name: FONT, size: 10, color: COLORS.redText },
    fill: COLORS.red,
    wrapText: true,
    verticalAlignment: "center",
  };
  sheet.getRange(`A3:${width}3`).format.rowHeight = 34;
}

function styleHeader(range) {
  range.format = {
    fill: COLORS.navy,
    font: { name: FONT, size: 10, bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "inside", style: "thin", color: "#FFFFFF" },
  };
  range.format.rowHeight = 30;
}

function applyBodyStyle(range) {
  range.format.font = { name: FONT, size: 10, color: COLORS.text };
  range.format.verticalAlignment = "center";
  range.format.borders = {
    insideHorizontal: { style: "thin", color: "#D9E2F3" },
    bottom: { style: "thin", color: COLORS.border },
  };
}

const r4 = await SpreadsheetFile.importXlsx(await FileBlob.load(r4WorkbookPath));
const r4Sheet = r4.worksheets.getItem("确认清单");
const r4Values = r4Sheet.getRange("A9:K128").values;
const r4EvidenceFormulas = r4Sheet.getRange("F9:F128").formulas;
const golden = JSON.parse(await fs.readFile(goldenPath, "utf8"));
const quality = JSON.parse(await fs.readFile(qualityPath, "utf8"));
const cases = golden.cases || [];
if (cases.length !== 120 || r4Values.length !== 120) {
  throw new Error("R5 requires exactly 120 aligned R4 and Golden Dataset rows");
}

const records = cases.map((item, index) => {
  const r4Row = r4Values[index];
  const taskId = String(r4Row[0] || "");
  const caseId = String(item.case_id || "");
  if (taskId.slice(-4) !== caseId.slice(-4)) {
    throw new Error(`R4/Golden row mismatch at index ${index + 1}`);
  }
  const expected = String(item.expected_classification || "");
  const explicit = parseExplicitClassification(r4Row[7]);
  if (explicit && explicit !== expected) {
    throw new Error(`R4 explicit conclusion conflicts with exported label: ${caseId}`);
  }
  const prediction = quality.predictions?.[caseId];
  const retrieval = quality.retrievals?.[caseId] || [];
  if (!prediction || !CLASSIFICATIONS[prediction.classification]) {
    throw new Error(`missing valid live prediction: ${caseId}`);
  }
  const expectedChunks = (item.expected_relevant_chunk_ids || []).map(String);
  const retrievedChunks = retrieval.map(String);
  const exactHit = expectedChunks.some((chunkId) => retrievedChunks.includes(chunkId));
  const expectedDocuments = new Set(expectedChunks.map(documentKey));
  const sameDocumentHit = retrievedChunks.some((chunkId) =>
    expectedDocuments.has(documentKey(chunkId)),
  );
  return {
    taskId,
    caseId,
    sourceType: String(item.source_type || ""),
    risk: String(r4Row[2] || ""),
    query: String(item.query || ""),
    r4Code: expected,
    r4Name: CLASSIFICATIONS[expected],
    explicitCode: explicit,
    explicitName: explicit ? CLASSIFICATIONS[explicit] : "",
    aiCode: String(prediction.classification),
    aiName: CLASSIFICATIONS[prediction.classification],
    evidenceFormula: r4EvidenceFormulas[index]?.[0] || "",
    reviewer: String(r4Row[8] || ""),
    reviewDate: String(r4Row[9] || ""),
    expectedChunks,
    retrievedChunks,
    exactHit,
    sameDocumentHit,
  };
});

const explicitRecords = records.filter((record) => record.explicitCode);
const conflictRecords = records.filter((record) => !record.explicitCode);
const groupMap = new Map();
for (const record of conflictRecords) {
  const key = `${record.r4Code}|${record.aiCode}`;
  if (!groupMap.has(key)) {
    groupMap.set(key, []);
  }
  groupMap.get(key).push(record);
}
const groups = [...groupMap.entries()]
  .sort(([left], [right]) => left.localeCompare(right))
  .map(([key, rows], index) => {
    const [r4Code, aiCode] = key.split("|");
    const preferAI = r4Code === "HUMAN_CONFIRMATION_REQUIRED";
    return {
      groupId: `GRP-${String(index + 1).padStart(2, "0")}`,
      r4Code,
      aiCode,
      r4Name: CLASSIFICATIONS[r4Code],
      aiName: CLASSIFICATIONS[aiCode],
      count: rows.length,
      recommendation: preferAI ? "采用本次AI" : "沿用R4",
      reason: preferAI
        ? "R4 为通用兜底分类；本次模型给出更具体分类。建议批量采用后抽查例外。"
        : "R4 非标准来自候选关键词规则。建议沿用 R4，并重点抽查证据边界。",
      rows,
    };
  });
const groupForCase = new Map(
  groups.flatMap((group) => group.rows.map((record) => [record.caseId, group.groupId])),
);

const reviewer = records.find((record) => record.reviewer)?.reviewer || "";
const workbook = Workbook.create();
const rulesSheet = workbook.worksheets.add("批量规则");
const conflictsSheet = workbook.worksheets.add("冲突确认");
const explicitSheet = workbook.worksheets.add("明确结论");
const auditSheet = workbook.worksheets.add("技术底稿");

configureSheet(rulesSheet, COLORS.navy);
configureSheet(conflictsSheet, "#5B9BD5");
configureSheet(explicitSheet, "#70AD47");
configureSheet(auditSheet, "#A5A5A5");

styleTitle(
  rulesSheet,
  "POC-03 Golden 标签批量确认",
  "只需确认下方 7 组规则。选择“确认使用AI建议批量规则”后，58 条冲突将按建议处理；如有例外，请在“冲突确认”逐条改写。",
  "H",
);
rulesSheet.getRange("A5:F7").values = [
  ["批量确认", "未确认", "确认人", reviewer, "确认日期", new Date("2026-09-18T00:00:00+08:00")],
  ["需复核项", conflictRecords.length, "分组数", groups.length, "已配置组", null],
  ["已由R4明确结论锁定", explicitRecords.length, "总记录", records.length, "待处理组", null],
];
rulesSheet.getRange("F6").formulas = [[`=COUNTIFS(G10:G${9 + groups.length},"<>待确认")`]];
rulesSheet.getRange("F7").formulas = [[`=COUNTIFS(G10:G${9 + groups.length},"待确认")`]];
rulesSheet.getRange("A5:A7").format.font = { name: FONT, bold: true };
rulesSheet.getRange("C5:C7").format.font = { name: FONT, bold: true };
rulesSheet.getRange("E5:E7").format.font = { name: FONT, bold: true };
rulesSheet.getRange("B5").format.fill = COLORS.amberStrong;
rulesSheet.getRange("D5:F5").format.fill = COLORS.amber;
rulesSheet.getRange("F5").format.numberFormat = "yyyy-mm-dd";
rulesSheet.getRange("A5:F7").format.verticalAlignment = "center";
rulesSheet.getRange("A5:F7").format.borders = {
  preset: "outside",
  style: "thin",
  color: COLORS.border,
};
rulesSheet.getRange("B5").dataValidation = {
  rule: { type: "list", values: ["未确认", "确认使用AI建议批量规则"] },
};

const groupHeaders = [
  "分组编号",
  "R4分类",
  "本次AI分类",
  "条数",
  "AI建议处理",
  "人工批量规则（可覆盖）",
  "生效规则",
  "说明",
];
rulesSheet.getRange("A9:H9").values = [groupHeaders];
styleHeader(rulesSheet.getRange("A9:H9"));
const groupStart = 10;
const groupRows = groups.map((group) => [
  group.groupId,
  group.r4Name,
  group.aiName,
  group.count,
  group.recommendation,
  "",
  null,
  group.reason,
]);
rulesSheet.getRangeByIndexes(groupStart - 1, 0, groupRows.length, 8).values = groupRows;
for (let index = 0; index < groups.length; index += 1) {
  const row = groupStart + index;
  rulesSheet.getRange(`G${row}`).formulas = [[
    `=IF(F${row}<>"",F${row},IF($B$5="确认使用AI建议批量规则",E${row},"待确认"))`,
  ]];
}
rulesSheet.getRange(`F${groupStart}:F${groupStart + groups.length - 1}`).dataValidation = {
  rule: {
    type: "list",
    values: ["沿用R4", "采用本次AI", "逐条确认", "暂不确认"],
  },
};
applyBodyStyle(rulesSheet.getRange(`A${groupStart}:H${groupStart + groups.length - 1}`));
rulesSheet.getRange(`F${groupStart}:F${groupStart + groups.length - 1}`).format.fill = COLORS.amber;
rulesSheet.getRange(`H${groupStart}:H${groupStart + groups.length - 1}`).format.wrapText = true;
rulesSheet.getRange(`A${groupStart}:G${groupStart + groups.length - 1}`).format.horizontalAlignment = "center";
rulesSheet.getRange(`G${groupStart}:G${groupStart + groups.length - 1}`).conditionalFormats.addCustom(
  `=OR(G${groupStart}="待确认",G${groupStart}="逐条确认",G${groupStart}="暂不确认")`,
  { fill: COLORS.red, font: { bold: true, color: COLORS.redText } },
);
rulesSheet.getRange("A:A").format.columnWidth = 13;
rulesSheet.getRange("B:C").format.columnWidth = 18;
rulesSheet.getRange("D:D").format.columnWidth = 9;
rulesSheet.getRange("E:G").format.columnWidth = 20;
rulesSheet.getRange("H:H").format.columnWidth = 52;
rulesSheet.freezePanes.freezeRows(9);

styleTitle(
  conflictsSheet,
  "需确认的 58 条标签冲突",
  "默认只读批量规则。仅当某条不适用时，在黄色“单条最终分类”选择分类并填写简短说明；点击证据可定位原文。",
  "L",
);
conflictsSheet.getRange("A5:F5").values = [[
  "需确认项",
  conflictRecords.length,
  "已确认",
  null,
  "待确认",
  null,
]];
const conflictStart = 9;
const conflictEnd = conflictStart + conflictRecords.length - 1;
conflictsSheet.getRange("D5").formulas = [[`=COUNTIFS(L${conflictStart}:L${conflictEnd},"已确认")`]];
conflictsSheet.getRange("F5").formulas = [[`=COUNTIFS(L${conflictStart}:L${conflictEnd},"待确认")`]];
conflictsSheet.getRange("A5:F5").format.font = { name: FONT, bold: true };
conflictsSheet.getRange("A5:F5").format.fill = COLORS.paleBlue;
const conflictHeaders = [
  "待办编号",
  "资料类别",
  "风险",
  "AI分析问题",
  "R4分类",
  "本次AI分类",
  "分组",
  "打开证据",
  "单条最终分类",
  "例外说明",
  "生效最终分类",
  "状态",
];
conflictsSheet.getRange("A8:L8").values = [conflictHeaders];
styleHeader(conflictsSheet.getRange("A8:L8"));
const conflictRows = conflictRecords.map((record) => [
  record.taskId,
  record.sourceType,
  record.risk,
  record.query,
  record.r4Name,
  record.aiName,
  groupForCase.get(record.caseId),
  null,
  "",
  "",
  null,
  null,
]);
conflictsSheet.getRangeByIndexes(conflictStart - 1, 0, conflictRows.length, 12).values = conflictRows;
for (let index = 0; index < conflictRecords.length; index += 1) {
  const row = conflictStart + index;
  const evidenceFormula = conflictRecords[index].evidenceFormula;
  if (evidenceFormula) {
    conflictsSheet.getRange(`H${row}`).formulas = [[evidenceFormula]];
  } else {
    conflictsSheet.getRange(`H${row}`).values = [["证据链接缺失"]];
  }
  conflictsSheet.getRange(`K${row}`).formulas = [[
    `=IF(I${row}<>"",I${row},IF(INDEX('批量规则'!$G$${groupStart}:$G$${groupStart + groups.length - 1},MATCH(G${row},'批量规则'!$A$${groupStart}:$A$${groupStart + groups.length - 1},0))="沿用R4",E${row},IF(INDEX('批量规则'!$G$${groupStart}:$G$${groupStart + groups.length - 1},MATCH(G${row},'批量规则'!$A$${groupStart}:$A$${groupStart + groups.length - 1},0))="采用本次AI",F${row},"")))`,
  ]];
  conflictsSheet.getRange(`L${row}`).formulas = [[`=IF(K${row}="","待确认","已确认")`]];
}
conflictsSheet.getRange(`I${conflictStart}:I${conflictEnd}`).dataValidation = {
  rule: { type: "list", values: CLASSIFICATION_NAMES },
};
applyBodyStyle(conflictsSheet.getRange(`A${conflictStart}:L${conflictEnd}`));
conflictsSheet.getRange(`D${conflictStart}:D${conflictEnd}`).format.wrapText = true;
conflictsSheet.getRange(`I${conflictStart}:J${conflictEnd}`).format.fill = COLORS.amber;
conflictsSheet.getRange(`H${conflictStart}:H${conflictEnd}`).format.font = {
  name: FONT,
  color: "#0563C1",
  underline: "single",
};
conflictsSheet.getRange(`L${conflictStart}:L${conflictEnd}`).conditionalFormats.addCustom(
  `=L${conflictStart}="待确认"`,
  { fill: COLORS.red, font: { bold: true, color: COLORS.redText } },
);
conflictsSheet.getRange(`L${conflictStart}:L${conflictEnd}`).conditionalFormats.addCustom(
  `=L${conflictStart}="已确认"`,
  { fill: COLORS.green, font: { bold: true, color: "#375623" } },
);
conflictsSheet.getRange("A:A").format.columnWidth = 13;
conflictsSheet.getRange("B:B").format.columnWidth = 23;
conflictsSheet.getRange("C:C").format.columnWidth = 8;
conflictsSheet.getRange("D:D").format.columnWidth = 46;
conflictsSheet.getRange("E:F").format.columnWidth = 16;
conflictsSheet.getRange("G:G").format.columnWidth = 10;
conflictsSheet.getRange("H:H").format.columnWidth = 15;
conflictsSheet.getRange("I:I").format.columnWidth = 18;
conflictsSheet.getRange("J:J").format.columnWidth = 28;
conflictsSheet.getRange("K:K").format.columnWidth = 18;
conflictsSheet.getRange("L:L").format.columnWidth = 11;
conflictsSheet.getRange(`${conflictStart}:${conflictEnd}`).format.rowHeight = 42;
conflictsSheet.freezePanes.freezeRows(8);
conflictsSheet.freezePanes.freezeColumns(1);

styleTitle(
  explicitSheet,
  "R4 已明确结论的 62 条记录",
  "这些记录的人工结论已明确写出最终分类，且与 R4 导出标签一致。本轮不要求重复确认，仅供追溯和抽查。",
  "G",
);
const explicitHeaders = [
  "待办编号",
  "资料类别",
  "AI分析问题",
  "人工明确分类",
  "本次AI分类",
  "打开证据",
  "处理状态",
];
explicitSheet.getRange("A5:G5").values = [explicitHeaders];
styleHeader(explicitSheet.getRange("A5:G5"));
const explicitStart = 6;
const explicitEnd = explicitStart + explicitRecords.length - 1;
explicitSheet.getRangeByIndexes(explicitStart - 1, 0, explicitRecords.length, 7).values = explicitRecords.map(
  (record) => [
    record.taskId,
    record.sourceType,
    record.query,
    record.explicitName,
    record.aiName,
    null,
    "沿用R4人工结论",
  ],
);
for (let index = 0; index < explicitRecords.length; index += 1) {
  const row = explicitStart + index;
  const evidenceFormula = explicitRecords[index].evidenceFormula;
  if (evidenceFormula) {
    explicitSheet.getRange(`F${row}`).formulas = [[evidenceFormula]];
  }
}
applyBodyStyle(explicitSheet.getRange(`A${explicitStart}:G${explicitEnd}`));
explicitSheet.getRange(`C${explicitStart}:C${explicitEnd}`).format.wrapText = true;
explicitSheet.getRange(`F${explicitStart}:F${explicitEnd}`).format.font = {
  name: FONT,
  color: "#0563C1",
  underline: "single",
};
explicitSheet.getRange(`G${explicitStart}:G${explicitEnd}`).format.fill = COLORS.green;
explicitSheet.getRange("A:A").format.columnWidth = 13;
explicitSheet.getRange("B:B").format.columnWidth = 23;
explicitSheet.getRange("C:C").format.columnWidth = 52;
explicitSheet.getRange("D:E").format.columnWidth = 18;
explicitSheet.getRange("F:F").format.columnWidth = 15;
explicitSheet.getRange("G:G").format.columnWidth = 20;
explicitSheet.getRange(`${explicitStart}:${explicitEnd}`).format.rowHeight = 38;
explicitSheet.freezePanes.freezeRows(5);
explicitSheet.freezePanes.freezeColumns(1);

styleTitle(
  auditSheet,
  "R5 技术底稿",
  "用于严格导入和失败诊断追溯。正文、向量和逐条模型响应不写入本表。",
  "L",
);
const auditHeaders = [
  "CaseId",
  "待办编号",
  "资料类别",
  "R4分类代码",
  "R4分类",
  "人工结论显式分类代码",
  "本次AI分类代码",
  "期望Chunk数",
  "Top5数",
  "精确Chunk命中",
  "同文档命中",
  "R5处理范围",
];
auditSheet.getRange("A5:L5").values = [auditHeaders];
styleHeader(auditSheet.getRange("A5:L5"));
const auditStart = 6;
const auditEnd = auditStart + records.length - 1;
auditSheet.getRangeByIndexes(auditStart - 1, 0, records.length, 12).values = records.map((record) => [
  record.caseId,
  record.taskId,
  record.sourceType,
  record.r4Code,
  record.r4Name,
  record.explicitCode || "",
  record.aiCode,
  record.expectedChunks.length,
  record.retrievedChunks.length,
  record.exactHit,
  record.sameDocumentHit,
  record.explicitCode ? "R4明确结论" : groupForCase.get(record.caseId),
]);
applyBodyStyle(auditSheet.getRange(`A${auditStart}:L${auditEnd}`));
auditSheet.getRange(`H${auditStart}:I${auditEnd}`).format.numberFormat = "0";
auditSheet.getRange(`J${auditStart}:K${auditEnd}`).format.horizontalAlignment = "center";
auditSheet.getRange("A:B").format.columnWidth = 14;
auditSheet.getRange("C:C").format.columnWidth = 23;
auditSheet.getRange("D:G").format.columnWidth = 28;
auditSheet.getRange("H:K").format.columnWidth = 14;
auditSheet.getRange("L:L").format.columnWidth = 18;
auditSheet.freezePanes.freezeRows(5);
auditSheet.freezePanes.freezeColumns(2);

for (const sheet of [rulesSheet, conflictsSheet, explicitSheet, auditSheet]) {
  const used = sheet.getUsedRange();
  used.format.verticalAlignment = "center";
}

workbook.recalculate();
await fs.mkdir(outputDir, { recursive: true });
const outputPath = path.join(outputDir, "POC-03-Golden标签轻量确认-R5.xlsx");
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

const saved = await SpreadsheetFile.importXlsx(await FileBlob.load(outputPath));
const validation = [];
for (const [sheetName, range] of [
  ["批量规则", `A1:H${groupStart + groups.length}`],
  ["冲突确认", "A1:L20"],
  ["明确结论", "A1:G16"],
  ["技术底稿", "A1:L16"],
]) {
  const inspected = await saved.inspect({
    kind: "table",
    range: `${sheetName}!${range}`,
    include: "values,formulas",
    tableMaxRows: 20,
    tableMaxCols: 12,
    maxChars: 16000,
  });
  validation.push(inspected.ndjson);
  const preview = await saved.render({
    sheetName,
    range,
    scale: 1.5,
    format: "png",
  });
  await fs.writeFile(
    path.join(outputDir, `preview-${sheetName}.png`),
    new Uint8Array(await preview.arrayBuffer()),
  );
}
const errors = await saved.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 300 },
  maxChars: 12000,
});
validation.push(errors.ndjson);
await fs.writeFile(path.join(outputDir, "artifact-tool-validation-r5.ndjson"), validation.join("\n"), "utf8");
const report = {
  schema_version: "poc-03.r5-label-review-package.v1",
  status: "AWAITING_HUMAN_CONFIRMATION",
  total_case_count: records.length,
  r4_explicit_conclusion_count: explicitRecords.length,
  conflict_review_count: conflictRecords.length,
  conflict_group_count: groups.length,
  output_workbook: path.basename(outputPath),
  privacy: {
    document_text_committed: false,
    vectors_committed: false,
    model_responses_committed: false,
    api_keys_committed: false,
  },
};
await fs.writeFile(
  path.join(outputDir, "r5-review-package-result.json"),
  `${JSON.stringify(report, null, 2)}\n`,
  "utf8",
);
console.log(JSON.stringify(report));
