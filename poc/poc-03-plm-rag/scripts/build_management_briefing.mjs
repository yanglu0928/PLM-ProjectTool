import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { FileBlob, Presentation, PresentationFile } from "@oai/artifact-tool";


const [deliveryPath, wbsPath, qualityPath, outputDir] = process.argv.slice(2);
if (!deliveryPath || !wbsPath || !qualityPath || !outputDir) {
  throw new Error("Usage: node build_management_briefing.mjs <delivery.json> <wbs.json> <quality.json> <output-dir>");
}
const { SKILL_DIR, RUNTIME_PYTHON } = process.env;
if (!path.isAbsolute(SKILL_DIR ?? "") || !path.isAbsolute(RUNTIME_PYTHON ?? "")) {
  throw new Error("Set absolute SKILL_DIR and RUNTIME_PYTHON");
}
const { resolvePresentationFont, applyPresentationChartFont, finalizePresentation } = await import(
  pathToFileURL(path.join(SKILL_DIR, "container_tools/artifact_tool_utils.mjs")).href,
);

const delivery = JSON.parse(await fs.readFile(deliveryPath, "utf8"));
const wbs = JSON.parse(await fs.readFile(wbsPath, "utf8"));
const quality = JSON.parse(await fs.readFile(qualityPath, "utf8"));
const isIndependentHoldout = quality.input?.dataset_kind === "independent_holdout";
const FONT = resolvePresentationFont({ fontFamily: "Microsoft YaHei" });
const C = {
  navy: "#17365D", blue: "#1F4E78", cyan: "#2F75B5", pale: "#DDEBF7",
  ink: "#172B4D", text: "#334155", muted: "#64748B", line: "#CBD5E1",
  green: "#2E7D32", greenPale: "#E8F5E9", amber: "#B45309", amberPale: "#FFF7E6",
  red: "#B42318", redPale: "#FDECEC", gray: "#F4F6F8", white: "#FFFFFF",
};
const W = 1280;
const H = 720;
const presentation = Presentation.create({ slideSize: { width: W, height: H } });

function addRect(slide, left, top, width, height, fill, radius = false) {
  return slide.shapes.add({
    geometry: radius ? "roundRect" : "rect",
    position: { left, top, width, height },
    fill,
    line: { fill: "none", width: 0 },
  });
}

function addText(slide, text, left, top, width, height, opts = {}) {
  const box = slide.shapes.add({
    geometry: "textbox",
    position: { left, top, width, height },
    fill: "none",
    line: { fill: "none", width: 0 },
  });
  box.text = String(text);
  box.text.style = {
    typeface: FONT,
    fontSize: opts.fontSize ?? 22,
    bold: opts.bold ?? false,
    color: opts.color ?? C.text,
    alignment: opts.align ?? "left",
    verticalAlignment: opts.vAlign ?? "top",
    autoFit: opts.autoFit ?? "shrinkText",
  };
  return box;
}

function baseSlide(title, kicker, page) {
  const slide = presentation.slides.add();
  slide.background.fill = C.white;
  addRect(slide, 0, 0, W, 12, C.blue);
  addText(slide, kicker, 72, 38, 720, 24, { fontSize: 13, bold: true, color: C.cyan });
  addText(slide, title, 72, 66, 1080, 54, { fontSize: 34, bold: true, color: C.navy });
  addRect(slide, 72, 126, 1136, 2, C.line);
  addText(slide, `PLM 项目实施辅助工具  ·  管理层汇报  ·  2026-09-21`, 72, 682, 1000, 20, { fontSize: 11, color: C.muted });
  addText(slide, String(page).padStart(2, "0"), 1138, 680, 70, 22, { fontSize: 12, bold: true, color: C.blue, align: "right" });
  return slide;
}

function addMetric(slide, value, label, left, top, color = C.navy, width = 220) {
  addText(slide, value, left, top, width, 58, { fontSize: 42, bold: true, color });
  addText(slide, label, left, top + 58, width, 42, { fontSize: 15, color: C.muted });
}

function note(slide, text) {
  slide.speakerNotes.textFrame.setText(text);
}

// 1. Cover
{
  const slide = presentation.slides.add();
  slide.background.fill = C.navy;
  addRect(slide, 0, 0, 18, H, "#62B5E5");
  addText(slide, "PLM 项目实施辅助工具", 82, 88, 740, 36, { fontSize: 20, bold: true, color: "#9DD8F3" });
  addText(slide, "项目实施分析与\n技术验证管理汇报", 82, 154, 870, 190, { fontSize: 52, bold: true, color: C.white });
  addText(slide, "第一批 5 个项目 · 内部交付包 R6 · 实施 WBS 草案 R7", 86, 374, 900, 34, { fontSize: 20, color: "#D7E7F3" });
  addRect(slide, 86, 448, 410, 96, "#214F78", true);
  addText(slide, "当前结论", 112, 465, 150, 24, { fontSize: 14, bold: true, color: "#9DD8F3" });
  addText(slide, "Phase 0 尚未关闭", 112, 494, 340, 34, { fontSize: 25, bold: true, color: C.white });
  addText(slide, "质量门槛未全部通过；正式编码与冻结仍受 Gate 约束", 86, 582, 980, 32, { fontSize: 18, color: "#F8D7DA" });
  addText(slide, "2026-09-21", 1050, 652, 150, 24, { fontSize: 14, color: "#C5D7E5", align: "right" });
  note(slide, "来源：internal-requirement-solution-delivery-package.json；implementation-wbs-draft.json；prompt-v2-live-quality-result.json。内部管理汇报，不构成正式项目基线。");
}

// 2. Executive status
{
  const slide = baseSlide("执行状态：交付准备已成形，质量 Gate 仍是主阻塞", "01 · 执行摘要", 2);
  addMetric(slide, "5", "项目范围已结构化", 78, 158);
  addMetric(slide, "40", "需求—方案交付项", 318, 158);
  addMetric(slide, "60", "实施 WBS 草案任务", 558, 158);
  addMetric(slide, "21", "专项设计项", 798, 158);
  addMetric(slide, "10", "正式化待办", 1038, 158, C.amber, 170);
  addRect(slide, 72, 300, 544, 310, C.greenPale);
  addText(slide, "已经具备", 100, 326, 220, 34, { fontSize: 24, bold: true, color: C.green });
  addText(slide, "• 五项目需求分类与解决方案一一追溯\n• 标准/非标/差异/待确认各 10 条\n• W0–W4 内部实施路线与角色职责\n• Windows 11 技术链路与真实模型调用证据", 100, 380, 470, 180, { fontSize: 19, color: C.text });
  addRect(slide, 664, 300, 544, 310, C.redPale);
  addText(slide, "仍未完成", 692, 326, 220, 34, { fontSize: 24, bold: true, color: C.red });
  addText(slide, "• 分类与引用质量门槛尚未通过\n• 50 条独立留出集已完成，但总状态为 FAIL\n• Architecture / Data Model / API Contract 尚未冻结\n• 正式资源、日历计划和实名责任人尚未排定", 692, 380, 470, 180, { fontSize: 19, color: C.text });
  note(slide, "来源：R6 内部交付包与 R7 WBS 草案。‘已具备’只指内部准备成果；正式状态仍受 Phase 0 和后续冻结 Gate 约束。");
}

// 3. Scope
{
  const slide = baseSlide("五项目范围已统一成 40 条可追溯交付项", "02 · 范围与需求", 3);
  addText(slide, "40", 72, 154, 240, 80, { fontSize: 66, bold: true, color: C.navy });
  addText(slide, "每个项目 8 条，共 5 个项目", 76, 232, 360, 34, { fontSize: 18, color: C.muted });
  const categories = [
    ["标准功能", "10", "优先以配置和标准能力交付", C.green],
    ["非标功能", "10", "进入专项设计、实现与验证", C.cyan],
    ["差异项", "10", "先验证差异和治理规则", C.amber],
    ["待确认项", "10", "先形成唯一书面决策", C.red],
  ];
  categories.forEach(([name, value, desc, color], i) => {
    const top = 300 + i * 76;
    addRect(slide, 72, top + 7, 8, 54, color);
    addText(slide, value, 102, top, 78, 52, { fontSize: 32, bold: true, color });
    addText(slide, name, 190, top + 2, 170, 28, { fontSize: 20, bold: true, color: C.ink });
    addText(slide, desc, 190, top + 32, 390, 28, { fontSize: 15, color: C.muted });
  });
  addRect(slide, 678, 164, 530, 408, C.gray);
  addText(slide, "项目组合", 708, 190, 240, 34, { fontSize: 24, bold: true, color: C.navy });
  const projectNames = delivery.projects.map((p) => p.project_name);
  addText(slide, projectNames.map((name, i) => `${String(i + 1).padStart(2, "0")}  ${name}`).join("\n\n"), 710, 246, 450, 265, { fontSize: 18, color: C.text });
  addText(slide, "边界：当前均为内部需求/方案草案，不等同正式需求或合同变更。", 708, 526, 450, 32, { fontSize: 14, bold: true, color: C.red });
  note(slide, "来源：R6 内部交付包 projects 与 delivery_items。类别计数：标准功能 10、非标功能 10、差异项 10、待确认项 10。");
}

// 4. Solution and delivery readiness
{
  const slide = baseSlide("解决方案已覆盖实施链条，但专项风险需前置治理", "03 · 方案与专项", 4);
  addMetric(slide, "21", "专项设计项", 78, 160);
  addMetric(slide, "6", "高风险交付项", 332, 160, C.red);
  addMetric(slide, "30", "推荐调研主题", 586, 160);
  addMetric(slide, "10", "正式化待办", 840, 160, C.amber);
  addMetric(slide, "0", "正式对象", 1094, 160, C.red, 114);
  addRect(slide, 72, 302, 1136, 2, C.line);
  addText(slide, "专项设计聚焦", 72, 334, 250, 34, { fontSize: 23, bold: true, color: C.navy });
  const specialtyCounts = new Map();
  for (const item of delivery.specialty_items) {
    const key = item.specialty_type || item.type || "其他专项";
    specialtyCounts.set(key, (specialtyCounts.get(key) || 0) + 1);
  }
  const specialtyText = [...specialtyCounts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6).map(([k, v]) => `${k}  ${v}`).join("\n");
  addText(slide, specialtyText || "接口、迁移、权限、领域专项", 72, 390, 360, 180, { fontSize: 18, color: C.text });
  addText(slide, "交付控制", 482, 334, 250, 34, { fontSize: 23, bold: true, color: C.navy });
  addText(slide, "• 正常、边界、失败恢复与审计场景\n• 明确进入条件、验收证据和排除项\n• 所有结果保留 Requirement / Solution / Delivery / Evidence 追溯", 482, 390, 620, 180, { fontSize: 19, color: C.text });
  addRect(slide, 72, 594, 1136, 46, C.amberPale);
  addText(slide, "管理含义：先完成决策与专项前置，不以“技术上可做”替代范围、责任和验收确认。", 92, 604, 1090, 28, { fontSize: 17, bold: true, color: C.amber });
  note(slide, "来源：R6 内部交付包 specialty_items、formalization_items、survey_outline。专项类型标签来自源数据，页面只展示数量最多的若干类。");
}

// 5. WBS roadmap
{
  const slide = baseSlide("实施草案按 W0–W4 推进，共 60 项任务", "04 · 实施路线", 5);
  const waves = [
    ["W0", "范围与决策收敛", wbs.summary.wave_counts.W0, C.red],
    ["W1", "标准能力配置", wbs.summary.wave_counts.W1, C.green],
    ["W2", "差异验证与治理", wbs.summary.wave_counts.W2, C.amber],
    ["W3", "非标与专项实现", wbs.summary.wave_counts.W3, C.cyan],
    ["W4", "验收、交接与正式化", wbs.summary.wave_counts.W4, C.navy],
  ];
  waves.forEach(([code, name, count, color], i) => {
    const left = 72 + i * 226;
    addRect(slide, left, 178, 198, 12, color);
    addText(slide, code, left, 212, 80, 38, { fontSize: 28, bold: true, color });
    addText(slide, name, left, 254, 198, 58, { fontSize: 19, bold: true, color: C.ink });
    addText(slide, `${count} 项任务`, left, 326, 150, 32, { fontSize: 18, color: C.muted });
  });
  addRect(slide, 72, 410, 1136, 150, C.gray);
  addText(slide, "WBS 设计原则", 98, 432, 220, 34, { fontSize: 22, bold: true, color: C.navy });
  addText(slide, "40 项需求交付任务 + 20 项项目控制任务；每个项目包含基线、联调、验收、交接四类控制任务。", 330, 432, 820, 34, { fontSize: 19, color: C.text });
  addText(slide, "当前刻意不填写实名、日期和承诺工期。Phase 0 与冻结 Gate 完成、资源确认后，才生成正式排期。", 98, 496, 1050, 38, { fontSize: 18, bold: true, color: C.red });
  note(slide, "来源：R7 implementation-wbs-draft.json。任务数：W0 15、W1 10、W2 10、W3 15、W4 10；总计 60。");
}

// 6. Quality metrics
{
  const slide = baseSlide("独立留出集：检索通过，分类与引用仍未达标", "05 · Phase 0 质量 Gate", 6);
  const actual = [quality.summary.top5_recall, quality.summary.classification_accuracy, quality.summary.citation_accuracy]
    .map((value) => Number((value * 100).toFixed(1)));
  const threshold = [quality.thresholds.top5_recall * 100, quality.thresholds.classification_accuracy * 100, quality.thresholds.citation_accuracy * 100];
  const chart = slide.charts.add("bar", {
    position: { left: 72, top: 166, width: 730, height: 420 },
    categories: ["Top-5 召回", "分类准确率", "引用准确率"],
    series: [
      { name: isIndependentHoldout ? "独立留出集实际" : "校准集实际", values: actual, fill: C.cyan },
      { name: "门槛", values: threshold, fill: C.line },
    ],
    barOptions: { direction: "bar", grouping: "clustered", gapWidth: 50 },
    hasLegend: true,
    legend: { position: "bottom", overlay: false, textStyle: { typeface: FONT, fontSize: 13, fill: C.text } },
    xAxis: { min: 0, max: 100, majorUnit: 20, numberFormatCode: "0'%'", majorGridlines: { style: "solid", fill: "#E2E8F0", width: 1 }, textStyle: { typeface: FONT, fontSize: 12, fill: C.muted } },
    yAxis: { textStyle: { typeface: FONT, fontSize: 14, fill: C.text }, line: { style: "solid", fill: C.line, width: 1 } },
    dataLabels: { showValue: true, position: "outEnd", textStyle: { typeface: FONT, fontSize: 12, bold: true, fill: C.ink } },
    chartFill: C.white,
    chartLine: { fill: "none", width: 0 },
    plotAreaFill: C.white,
  });
  applyPresentationChartFont(chart, { fontFamily: FONT });
  addRect(slide, 848, 174, 360, 118, C.redPale);
  addText(slide, isIndependentHoldout ? "独立留出集总状态" : "校准集总状态", 874, 194, 300, 24, { fontSize: 15, bold: true, color: C.red });
  addText(slide, "FAIL", 874, 226, 300, 48, { fontSize: 38, bold: true, color: C.red });
  addRect(slide, 848, 316, 360, 132, C.greenPale);
  addText(slide, "50 条真实复验", 874, 338, 300, 26, { fontSize: 18, bold: true, color: C.green });
  addText(slide, "已完成", 874, 378, 300, 34, { fontSize: 23, bold: true, color: C.ink });
  addText(slide, "Reranker 50/50；DeepSeek 50/50\n缺失预测 0；越界引用 0", 874, 418, 296, 52, { fontSize: 14, color: C.muted });
  addRect(slide, 848, 486, 360, 100, C.gray);
  addText(slide, "门槛保持不变", 874, 504, 300, 24, { fontSize: 16, bold: true, color: C.navy });
  addText(slide, "95% / 90% / 98%", 874, 538, 300, 34, { fontSize: 24, bold: true, color: C.navy });
  note(slide, `来源：holdout-live-quality-result.json。${quality.summary.case_count} 条独立留出集：Top-5 ${(quality.summary.top5_recall * 100).toFixed(2)}%（门槛 ${(quality.thresholds.top5_recall * 100).toFixed(0)}%）、分类 ${(quality.summary.classification_accuracy * 100).toFixed(2)}%（门槛 ${(quality.thresholds.classification_accuracy * 100).toFixed(0)}%）、引用 ${(quality.summary.citation_accuracy * 100).toFixed(2)}%（门槛 ${(quality.thresholds.citation_accuracy * 100).toFixed(0)}%）；总状态 ${quality.status}。`);
}

// 7. Risks
{
  const slide = baseSlide("四项管理风险决定下一阶段能否进入正式化", "06 · 风险与控制", 7);
  const risks = [
    ["01", "质量 Gate 未关闭", "独立留出集分类 48%、引用 74%，仍低于 90% 和 98% 门槛。", "保持 FAIL；冻结本轮结果，不降门槛。", C.red],
    ["02", "10 项业务事实待正式化", "内部工作基线尚未转为正式需求与验收责任。", "逐项形成唯一书面结论并升版。", C.amber],
    ["03", "6 项高风险交付", "接口、迁移、权限或专项前置可能形成连锁阻塞。", "W0/W2 前置验证，W3 才实施。", C.red],
    ["04", "平台验证不完整", "本轮质量链仅 Windows 11；Debian 13 按用户要求暂缓。", "正式发布前补齐目标平台证据矩阵。", C.cyan],
  ];
  risks.forEach(([num, name, impact, control, color], i) => {
    const top = 164 + i * 112;
    addText(slide, num, 76, top + 4, 52, 40, { fontSize: 26, bold: true, color });
    addText(slide, name, 144, top, 300, 32, { fontSize: 21, bold: true, color: C.ink });
    addText(slide, impact, 444, top, 390, 62, { fontSize: 16, color: C.text });
    addText(slide, control, 872, top, 306, 62, { fontSize: 16, bold: true, color });
    addRect(slide, 72, top + 84, 1136, 1, C.line);
  });
  note(slide, "来源：R6 内部交付包风险统计、R7 WBS 边界、当前真实复验执行状态。平台结论仅陈述本轮质量链范围，不否定已完成的其他 PoC 平台验证。");
}

// 8. Decisions / next
{
  const slide = baseSlide("下一阶段：质量修复与全新留出集复验", "07 · 管理决策与下一步", 8);
  const actions = [
    ["1", "接受本轮 FAIL 结论", "冻结 98% / 48% / 74% 结果，不修改门槛、人工标签或引用真值。", "立即"],
    ["2", "开展失败分层诊断", "本地分析 26 条分类失例、13 条引用失例和 1 条检索失例。", "立即"],
    ["3", "修复分类与引用链", "使用独立开发集调整业务判定、Prompt 和可接受引用集合。", "下一轮"],
    ["4", "建立全新独立留出集", "本轮 50 条已成为已见测试集，不能继续用于未见集通过声明。", "修复后"],
    ["5", "完成冻结与正式 WBS", "按 Architecture、Data Model、API Contract 顺序通过 Gate，再确认资源和日历计划。", "Phase 0 后"],
  ];
  actions.forEach(([num, name, detail, when], i) => {
    const top = 158 + i * 92;
    addRect(slide, 72, top, 54, 54, i === 0 ? C.red : C.blue, true);
    addText(slide, num, 72, top + 8, 54, 36, { fontSize: 23, bold: true, color: C.white, align: "center" });
    addText(slide, name, 152, top, 250, 32, { fontSize: 21, bold: true, color: C.ink });
    addText(slide, detail, 408, top, 620, 60, { fontSize: 16, color: C.text });
    addText(slide, when, 1072, top + 6, 116, 30, { fontSize: 16, bold: true, color: i === 0 ? C.red : C.blue, align: "right" });
  });
  addRect(slide, 72, 628, 1136, 38, C.navy);
  addText(slide, "推荐状态：保持 Phase 0，完成质量修复并通过全新独立留出集后再进入冻结。", 92, 634, 1096, 26, { fontSize: 17, bold: true, color: C.white });
  note(slide, "管理建议基于本轮 50 条独立留出集真实结果。该留出集已被使用，后续调优不得再次把它作为未见独立集的通过证据。");
}

await fs.mkdir(outputDir, { recursive: true });
const finalPath = path.join(outputDir, "PLM项目实施分析与技术验证管理汇报-R9.pptx");
const stagingDir = path.join(path.dirname(outputDir), ".management-briefing-r9-validation");
await fs.mkdir(stagingDir, { recursive: true });
const candidatePath = path.join(stagingDir, "candidate.pptx");
await (await PresentationFile.exportPptx(presentation)).save(candidatePath);

const requirements = {
  explicitTotalSlideCount: 8,
  requiredNativeTableOwnerSlides: [],
  requiredNativeChartOwnerSlides: [6],
  materializeLiteralChartWorkbooks: true,
  nativeChartTargetApplication: "powerpoint",
};
const result = await finalizePresentation({
  ...requirements,
  workspaceDir: path.dirname(path.dirname(path.dirname(outputDir))),
  candidatePath,
  finalPath,
  pythonExecutable: RUNTIME_PYTHON,
  integrityValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_layout_geometry.py"),
  layoutArgs: ["--expected-slide-size-emu", "12192000,6858000", "--validate-heading-fit"],
  requiredNativeTableOwnerSlides: [],
  fontPolicy: { basis: "design", families: [FONT] },
  verifyArtifactToolImport: true,
  receiptPath: path.join(stagingDir, "PLM项目实施分析与技术验证管理汇报-R9.validation.json"),
});

const checked = await PresentationFile.importPptx(await FileBlob.load(finalPath));
const renderDir = path.join(outputDir, "rendered");
await fs.mkdir(renderDir, { recursive: true });
for (let i = 0; i < checked.slides.items.length; i += 1) {
  const preview = await checked.export({ slide: checked.slides.items[i], format: "png", scale: 1 });
  await fs.writeFile(path.join(renderDir, `slide-${String(i + 1).padStart(2, "0")}.png`), new Uint8Array(await preview.arrayBuffer()));
  const layout = await checked.export({ slide: checked.slides.items[i], format: "layout" });
  await fs.writeFile(path.join(renderDir, `slide-${String(i + 1).padStart(2, "0")}.layout.json`), await layout.text());
}
await fs.writeFile(path.join(outputDir, "deck-result.json"), JSON.stringify({
  output_path: finalPath,
  slide_count: checked.slides.items.length,
  status: "MANAGEMENT_BRIEFING_READY_WITH_HOLDOUT_FAIL",
  quality_status: quality.status,
  holdout_live_status: "COMPLETED_FAIL",
  finalizer: result,
}, null, 2), "utf8");
console.log(JSON.stringify({ outputPath: finalPath, slideCount: checked.slides.items.length, qualityStatus: quality.status, holdoutLiveStatus: "COMPLETED_FAIL" }));
