# PLT-PKG-01-A09-P01：Windows 11 非发行统一候选输入矩阵

日期：2026-10-01；状态：`INPUTS_PINNED / ASSEMBLY_NOT_YET_RUN`。

## 编码前检查与范围

- 当前 Phase/WBS：Phase 2 / `PLT-PKG-01-A09-P01`。
- 输入基线：Gate 2 冻结提交 `64cdf09`；CR-PKG-004；既有 Windows 嵌入式、OCR 原生组件和 Paddle 模型非发行候选。无冻结 API/Schema 或技术栈变更。
- 前置任务：93 项旧候选、106 项联合 OCR 嵌入式运行时、34 项无 JBIG Tesseract 字节/来源矩阵分别完成内部验证；正式发行许可/签名/目标账户仍开放，不作为本次**非发行输入核对**的通过条件。
- 涉及模块：离线打包输入，不改运行中后端/前端、Parser、安装器或升级器。实体/API/权限：均无。
- 验收标准：每种输入固定 SHA-256、明确取舍和目标路径；拒绝旧 Tesseract/JBIG 字节混入；34/34 Hash 与新矩阵相同；缺项不宣称可发行。
- 风险与回滚：固定临时构建路径丢失时本任务仍有历史证据，但后续合包必须失败关闭并重新核源；仅弃用新产物，保留历史 ZIP/CSV，无数据迁移。

## 固定输入

| 输入 | 位置与 SHA-256 / 件数 | 进入新候选的规则 |
|---|---|---|
| 既有前端/许可候选 | `artifacts/package-prep/windows11/embedded-full-notice-candidate-ad21bbbee647/NOT-FOR-RELEASE-windows11-embedded-candidate.zip`；`6b42945167c4d93330a058f0550a4f8dfd26277287c7a7cf07c536ce400fd77a` | 仅复用 `payload/frontend/dist/` 3件、示例配置、现有第三方许可材料；丢弃该包93项旧 `payload/runtime/` 和旧顶层manifest/hash/inventory，重新生成。旧许可材料只代表原来审核范围，不能覆盖新增13项。 |
| 联合 OCR 运行时 | `artifacts/package-prep/windows11/embedded-backend-20261001-033602-abc36560/runtime`；106项 `.dist-info`、`METADATA` 106/106；目录内容不是单一文件 Hash，须在组装时逐件 Hash 并在输出清单固定 | 完整替换旧运行时。排除构建缓存和 `packages/bin`，保留私有 `python313._pth`；不能误用同日期另一个仅93项的运行时。 |
| 旧 OCR 原生候选 | `artifacts/package-prep/windows11/NOT-FOR-RELEASE-windows11-ocr-native.zip`；`b1dadde7993cd7dca7d1a26d58b7322cca5e59f03bdb11a4a3712213a73ad24b` | 仅取 `payload/ocr/ghostscript/` 654件及 `payload/ocr/tesseract/tessdata/` 41件；明确丢弃旧 Tesseract 的其他102件，包括旧 `tesseract.exe`/DLL/JBIG。原生 ZIP 的旧 manifest 不继承。 |
| 无 JBIG Tesseract | `C:/Users/17231/AppData/Local/Temp/plm-tesseract-msys2-jbigfree-20261001`；34个 PE，按下述 CSV 固定逐件 Hash；新 `libtiff-6.dll` 为 `3a8255fa962a84412954dc811452cb7dfe7e0b5aea6297931d4cdd0b665d72b0` | 34件放入 `payload/ocr/tesseract/` 根，配上旧候选的41件 tessdata；绝不包含 `libjbig-0.dll`。对应来源矩阵 `docs/progress/plt-pkg-01-a08-p09-p05-p03-a07-p03-no-jbig-license-evidence.csv` SHA-256 `a16312f5a322e21ad1f818fa7848a6f2b8f9f000add3b893f2b3a1e02fed15bc`。 |
| Paddle 模型 | `artifacts/package-prep/windows11/NOT-FOR-RELEASE-paddle-models-v5.zip`；`944ec7f8f7b7815ec9c35443afe980ad5207a5ed653c55cde573fd5e20c06c69` | 将 `models/` 内容映射至 `payload/ocr/models/`；旧模型 manifest 不继承，重新生成整体清单。 |

本机复核：三个 ZIP 的文件 SHA-256 与上表相同；新矩阵34行与候选34个 PE 的逐件 SHA-256 一致（0 mismatch）；联合运行时106/106 `.dist-info/METADATA` 存在。原生 ZIP 内旧 Tesseract 的102件不应进入新包。该复核不等于完整合包、清洁解包、OCR 运行、NOTICE/AGPL 分发审查或三平台正式验收。

下一任务 `PLT-PKG-01-A09-P02` 应实现严格输入验证、逐件去重/Hash/非发行清单、全新 ZIP 和清洁解包回归；不得覆盖旧候选。新13项 Python 许可文本和其他原生组件法律义务仍需后续单独审查。`release_eligible=false`。
