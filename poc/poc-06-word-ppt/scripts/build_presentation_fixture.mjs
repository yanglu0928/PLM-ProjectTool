import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const SKILL_DIR = process.env.SKILL_DIR;
const POC_DIR = process.env.POC_DIR;
const RUNTIME_PYTHON = process.env.RUNTIME_PYTHON;
if (!SKILL_DIR || !POC_DIR || !RUNTIME_PYTHON) {
  throw new Error("SKILL_DIR, POC_DIR and RUNTIME_PYTHON are required");
}

const { finalizePresentation } = await import(
  pathToFileURL(path.join(SKILL_DIR, "container_tools/artifact_tool_utils.mjs")).href,
);

const FONT = "Microsoft YaHei";
const WIDTH = 1280;
const HEIGHT = 720;
const NAVY = "#15324A";
const BLUE = "#2D6F9F";
const CYAN = "#3DA5C5";
const PALE = "#EAF2F8";
const GRAY = "#5D6B78";
const LIGHT = "#F6F8FA";

const presentation = Presentation.create({ slideSize: { width: WIDTH, height: HEIGHT } });
const imageBytes = new Uint8Array(await fs.readFile(path.join(POC_DIR, "input", "plm-collaboration.png")));

function addText(slide, text, position, style = {}) {
  const box = slide.shapes.add({
    geometry: "textbox",
    position,
    fill: "none",
    line: { fill: "none", width: 0 },
  });
  box.text = text;
  box.text.style = {
    typeface: FONT,
    fontSize: style.fontSize ?? 22,
    bold: style.bold ?? false,
    color: style.color ?? NAVY,
    autoFit: "shrinkText",
    verticalAlignment: style.verticalAlignment ?? "middle",
    textAlignment: style.textAlignment ?? "left",
  };
  return box;
}

function baseSlide(title, slideNumber) {
  const slide = presentation.slides.add();
  slide.background.fill = "#FFFFFF";
  addText(slide, title, { left: 72, top: 42, width: 1080, height: 70 }, { fontSize: 34, bold: true });
  const divider = slide.shapes.add({
    geometry: "line",
    position: { left: 72, top: 122, width: 1136, height: 0 },
    fill: "none",
    line: { style: "solid", fill: "#C7D3DD", width: 1 },
  });
  divider.sendToBack();
  addText(slide, String(slideNumber).padStart(2, "0"), { left: 1150, top: 650, width: 58, height: 28 }, { fontSize: 14, color: GRAY, textAlignment: "right" });
  return slide;
}

function addBodySlide(slideNumber) {
  const chapter = Math.floor((slideNumber - 2) / 10) + 1;
  const item = ((slideNumber - 2) % 10) + 1;
  const slide = baseSlide(`${chapter}.${item}  合成验证场景 ${String(slideNumber).padStart(2, "0")}`, slideNumber);
  addText(
    slide,
    `本页验证中文文本、章节结构和可编辑对象。场景 ${slideNumber} 使用确定性合成内容，不引用客户项目或合同资料。`,
    { left: 92, top: 165, width: 1050, height: 90 },
    { fontSize: 24, color: NAVY },
  );
  const lines = [
    `章节定位：第 ${chapter} 章，第 ${item} 个主题`,
    "内容范围：产品结构、文档版本、变更与交付证据",
    "验证目标：中文字体、换行、对象编辑性和 Office 打开性",
    "数据边界：全部字段均为合成测试数据",
  ];
  addText(slide, lines.join("\n\n"), { left: 120, top: 285, width: 980, height: 270 }, { fontSize: 21, color: GRAY });
  return slide;
}

const cover = presentation.slides.add();
cover.background.fill = LIGHT;
addText(cover, "PLM 项目实施辅助工具", { left: 90, top: 160, width: 1100, height: 90 }, { fontSize: 48, bold: true });
addText(cover, "50 页 PowerPoint 兼容性与版式验证样例", { left: 94, top: 270, width: 1050, height: 56 }, { fontSize: 27, color: BLUE });
addText(cover, "POC-06.1  纯合成内容", { left: 96, top: 360, width: 700, height: 38 }, { fontSize: 18, color: GRAY });

for (let slideNumber = 2; slideNumber <= 50; slideNumber += 1) {
  if (slideNumber === 10) {
    const slide = baseSlide("2.9  可编辑数据表", slideNumber);
    const table = slide.tables.add({
      rows: 5,
      columns: 4,
      left: 110,
      top: 180,
      width: 1060,
      height: 350,
      values: [
        ["对象", "版本", "状态", "责任域"],
        ["产品结构 A", "A.1", "受控", "设计"],
        ["工艺路线 B", "B.2", "评审", "工艺"],
        ["变更记录 C", "C.3", "归档", "项目"],
        ["交付证据 D", "D.4", "完成", "质量"],
      ],
    });
    table.styleOptions = { headerRow: true, bandedRows: true };
    table.borders.assign({ style: "solid", fill: "#CBD5DF", width: 1 });
    for (let column = 0; column < 4; column += 1) {
      table.getCell(0, column).fill = NAVY;
      table.getCell(0, column).text.style = { typeface: FONT, fontSize: 18, bold: true, color: "#FFFFFF" };
    }
    for (let row = 1; row < 5; row += 1) {
      for (let column = 0; column < 4; column += 1) {
        table.getCell(row, column).text.style = { typeface: FONT, fontSize: 17, color: NAVY };
      }
    }
  } else if (slideNumber === 11) {
    const slide = baseSlide("2.10  项目实施流程", slideNumber);
    const labels = ["需求确认", "方案设计", "实施验证", "验收归档"];
    const nodes = labels.map((label, index) => {
      const shape = slide.shapes.add({
        geometry: "roundRect",
        position: { left: 95 + index * 285, top: 270, width: 220, height: 105 },
        fill: index % 2 === 0 ? PALE : "#D8EEF4",
        line: { style: "solid", fill: BLUE, width: 2 },
        borderRadius: "rounded-xl",
      });
      shape.text = label;
      shape.text.style = { typeface: FONT, fontSize: 23, bold: true, color: NAVY, textAlignment: "center", verticalAlignment: "middle" };
      return shape;
    });
    for (let index = 0; index < nodes.length - 1; index += 1) {
      slide.shapes.connect(nodes[index], nodes[index + 1], {
        kind: "straight",
        fromSide: "right",
        toSide: "left",
        line: { style: "solid", fill: CYAN, width: 3 },
        head: { type: "arrow", width: "med", length: "med" },
      });
    }
    addText(slide, "所有节点和连接线均保持为 PowerPoint 原生可编辑对象", { left: 225, top: 450, width: 830, height: 48 }, { fontSize: 19, color: GRAY, textAlignment: "center" });
  } else if (slideNumber === 12) {
    const slide = baseSlide("3.1  合成工作量分布", slideNumber);
    const data = [
      { label: "需求", value: 18 },
      { label: "设计", value: 24 },
      { label: "实施", value: 31 },
      { label: "验收", value: 15 },
    ];
    data.forEach((item, index) => {
      const top = 185 + index * 92;
      addText(slide, item.label, { left: 145, top, width: 105, height: 46 }, { fontSize: 20, bold: true });
      slide.shapes.add({
        geometry: "roundRect",
        position: { left: 265, top: top + 4, width: item.value * 22, height: 38 },
        fill: index % 2 === 0 ? BLUE : CYAN,
        line: { fill: "none", width: 0 },
        borderRadius: "rounded-xl",
      });
      addText(slide, String(item.value), { left: 280 + item.value * 22, top, width: 70, height: 46 }, { fontSize: 18, bold: true, color: GRAY });
    });
    addText(slide, "所有数据条、标签和数值均为 PowerPoint 可编辑矢量对象", { left: 180, top: 570, width: 920, height: 42 }, { fontSize: 17, color: GRAY, textAlignment: "center" });
  } else if (slideNumber === 15) {
    const slide = baseSlide("3.4  工业研发协同场景", slideNumber);
    slide.images.add({
      blob: imageBytes,
      contentType: "image/png",
      alt: "三名工程师查看机械装配结构的合成插图",
      fit: "cover",
      position: { left: 120, top: 165, width: 1040, height: 430 },
      geometry: "roundRect",
      borderRadius: "rounded-xl",
    });
  } else {
    addBodySlide(slideNumber);
  }
}

const buildDir = path.join(POC_DIR, "build", "ppt");
const outputDir = path.join(POC_DIR, "output");
await fs.mkdir(buildDir, { recursive: true });
await fs.mkdir(outputDir, { recursive: true });
const candidatePath = path.join(buildDir, "poc06-50-slide-candidate.pptx");
const finalPath = path.join(outputDir, "POC-06-50-Slide-Compatibility.pptx");
await (await PresentationFile.exportPptx(presentation)).save(candidatePath);

const result = await finalizePresentation({
  explicitTotalSlideCount: 50,
  requiredNativeTableOwnerSlides: [10],
  requiredNativeChartOwnerSlides: [],
  workspaceDir: POC_DIR,
  candidatePath,
  finalPath,
  pythonExecutable: RUNTIME_PYTHON,
  integrityValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_layout_geometry.py"),
  layoutArgs: [
    "--expected-slide-size-emu", "12192000,6858000",
    "--validate-heading-fit",
    "--require-native-table-slide", "10",
  ],
  fontPolicy: { basis: "design", families: [FONT] },
  verifyArtifactToolImport: true,
  receiptPath: path.join(buildDir, "poc06-50-slide.validation.json"),
});
console.log(JSON.stringify({ finalPath, warnings: result.warnings ?? [] }));
