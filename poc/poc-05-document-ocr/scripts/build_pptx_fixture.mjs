import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const required = ["SKILL_DIR", "TMP_DIR", "FINAL_PPTX", "RUNTIME_PYTHON", "WORKSPACE_DIR"];
for (const name of required) {
  if (!process.env[name] || !path.isAbsolute(process.env[name])) {
    throw new Error(`${name} must be an absolute path`);
  }
}
const { SKILL_DIR, TMP_DIR, FINAL_PPTX, RUNTIME_PYTHON, WORKSPACE_DIR } = process.env;
const { finalizePresentation } = await import(
  pathToFileURL(path.join(SKILL_DIR, "container_tools/artifact_tool_utils.mjs")).href,
);
await fs.mkdir(TMP_DIR, { recursive: true });
await fs.mkdir(path.dirname(FINAL_PPTX), { recursive: true });

const fontFamily = "Microsoft YaHei";
const presentation = Presentation.create({ slideSize: { width: 1280, height: 720 } });

function addTitle(slide, text) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    name: "title",
    position: { left: 72, top: 54, width: 1136, height: 70 },
    fill: "none",
    line: { fill: "none", width: 0 },
  });
  shape.text = text;
  shape.text.style = {
    typeface: fontFamily,
    fontSize: 38,
    bold: true,
    color: "#000000",
    autoFit: "none",
  };
}

const slide1 = presentation.slides.add();
slide1.background.fill = "#FFFFFF";
addTitle(slide1, "项目概况");
const intro = slide1.shapes.add({
  geometry: "textbox",
  name: "body",
  position: { left: 88, top: 168, width: 1080, height: 360 },
  fill: "#EAF2F8",
  line: { fill: "#D9D9D9", width: 1 },
});
intro.text = "POC 05 统一解析测试\n项目名称：PLM 项目实施辅助工具\n项目编号：PLM-2026-005\n当前里程碑：需求确认";
intro.text.style = {
  typeface: fontFamily,
  fontSize: 26,
  color: "#142735",
  autoFit: "shrinkText",
};
slide1.speakerNotes.textFrame.setText("Self-generated POC-05 fixture. No external source.");

const slide2 = presentation.slides.add();
slide2.background.fill = "#FFFFFF";
addTitle(slide2, "交付清单");
const table = slide2.tables.add({
  rows: 4,
  columns: 3,
  left: 90,
  top: 170,
  width: 1100,
  height: 330,
  columnWidths: [300, 450, 350],
  values: [
    ["交付物", "标识", "状态"],
    ["统一解析结果", "PLM-2026-005", "待验证"],
    ["来源定位", "需求确认", "待验证"],
    ["人工复核", "客户确认", "待验证"],
  ],
});
table.styleOptions = { headerRow: true, bandedRows: true };
table.borders.assign({ style: "solid", fill: "#D9D9D9", width: 1 });
table.cells.block({ row: 0, column: 0, rowCount: 1, columnCount: 3 }).assign({
  fill: "#1F4E78",
  textStyle: { typeface: fontFamily, fontSize: 22, bold: true, color: "#FFFFFF" },
  anchor: "center",
});
table.cells.block({ row: 1, column: 0, rowCount: 3, columnCount: 3 }).assign({
  textStyle: { typeface: fontFamily, fontSize: 20, color: "#000000" },
  anchor: "center",
});
table.cells.block({ row: 2, column: 0, rowCount: 1, columnCount: 3 }).fill = "#EAF2F8";
slide2.speakerNotes.textFrame.setText("Self-generated POC-05 fixture. Native table required.");

const candidatePath = path.join(TMP_DIR, "candidate.pptx");
await (await PresentationFile.exportPptx(presentation)).save(candidatePath);
const result = await finalizePresentation({
  explicitTotalSlideCount: 2,
  requiredNativeTableOwnerSlides: [2],
  requiredNativeChartOwnerSlides: [],
  workspaceDir: WORKSPACE_DIR,
  candidatePath,
  finalPath: FINAL_PPTX,
  pythonExecutable: RUNTIME_PYTHON,
  integrityValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_layout_geometry.py"),
  layoutArgs: [
    "--expected-slide-size-emu", "12192000,6858000",
    "--validate-bullet-geometry",
    "--validate-heading-fit",
    "--require-native-table-slide", "2",
  ],
  fontPolicy: { basis: "design", families: [fontFamily] },
  verifyArtifactToolImport: true,
  receiptPath: path.join(TMP_DIR, "sample.pptx.validation.json"),
});
console.log(JSON.stringify(result));
