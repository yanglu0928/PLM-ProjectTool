import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const inputPath = process.env.INPUT_PPTX;
const outputDir = process.env.PREVIEW_DIR;
if (!inputPath || !path.isAbsolute(inputPath) || !outputDir || !path.isAbsolute(outputDir)) {
  throw new Error("INPUT_PPTX and PREVIEW_DIR must be absolute paths");
}
await fs.mkdir(outputDir, { recursive: true });
const presentation = await PresentationFile.importPptx(await FileBlob.load(inputPath));
for (let index = 0; index < 2; index += 1) {
  const slide = presentation.slides.items[index];
  const preview = await presentation.export({ slide, format: "png", scale: 2 });
  await fs.writeFile(
    path.join(outputDir, `final-slide-${index + 1}.png`),
    new Uint8Array(await preview.arrayBuffer()),
  );
}
