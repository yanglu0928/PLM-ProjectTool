# PLT-PKG-01-A09-P02：Windows 11 统一非发行候选组装与清洁解包

日期：2026-10-01；状态：`INTERNAL_INTEGRITY_PASS / RELEASE_BLOCKED`。

## 编码前检查

- 当前 Phase/WBS：Phase 2 / `PLT-PKG-01-A09-P02`。输入基线：Gate 2 冻结 `64cdf09`、CR-PKG-004、[A09-P01 输入矩阵](plt-pkg-01-a09-p01-unified-windows-input-matrix.md)。前置输入均已固定且本机可读。
- 涉及模块：`tools/package_windows_unified_candidate.py` 及独立解包核验器；不改正式后端/前端、Parser、服务、安装/升级程序。实体/API/权限：无；Migration：无。
- 验收标准：五类固定输入逐源验 Hash/件数；全新非发行 ZIP、不覆盖旧候选；只取旧 OCR ZIP 的 Ghostscript/tessdata，不取旧 Tesseract/JBIG；106项 Python 元数据和34项无JBIG PE；ZIP 内和清洁解包后19,449件逐件Hash吻合；工具负例拒绝。
- 风险/回滚：旧候选许可材料并未覆盖新增13项及新原生组件，Ghostscript AGPL/相应源码和产品 LICENSE/NOTICE 仍待审；放弃 Git 忽略的新候选即可回滚，不触碰用户数据或冻结合同。

## 结果

- 新 ZIP：`artifacts/package-prep/windows11/unified-candidate-fe9b2516b150/NOT-FOR-RELEASE-windows11-unified-candidate.zip`，461,974,579 字节，SHA-256 `da285e1c88d45f195d141f5eb6cba5f887f019063f4547a0a54ecae78c251bff`。该产物为本机 Git 忽略的测试候选，**未同步至 GitHub，也不可向客户发行**；工具、测试和此记录同步。
- 输入：旧前端/许可候选、106项联合运行时、原生 ZIP 的654项 Ghostscript+41项 tessdata、34项无JBIG Tesseract、10项 Paddle 模型。打包前核固定 ZIP SHA、无JBIG CSV SHA、34/34 PE Hash。旧 OCR ZIP 的其他102项 Tesseract 文件和93项旧运行时均不进入新包。
- 载荷19,449件；生成 `manifest.json`（`release_eligible=false`）、`payload-sha256sums.txt`、106项 Python 许可元数据清单。ZIP 写完后19,449件逐件重新读出验 Hash，清单/文件集一致。
- 首次清洁解包实际有19,452个文件；先做模块导入后产生约3,230个 `__pycache__`，使“空目录原始文件集”验收受污染。第二次在独立新空目录解包，**先**以 Windows 长路径方式逐件 Hash 和完整文件集验收，结果 `CLEAN_EXTRACT_HASH_PASS`，19,449/19,449，无缺项/额外项。长路径处理必需：`pypdfium2` 许可文本中有超过传统 Windows 路径长度的文件。
- 第一份解包目录中嵌入式 Python 3.13 的 `plm_assistant`、FastAPI、psycopg、Paddle/PaddleOCR/PaddleX、OCRmyPDF 导入退出0，版本 `0.1.0.dev0`；Tesseract 5.5.3 可运行、根目录34项 PE、`libjbig-0.dll` 不存在；Ghostscript 命令显示10.08.0。此为组件烟测，不等于 OCR 端到端或正式安装。
- 工具单测4/4通过：旧Tesseract不选入、输入计数变化拒绝、路径穿越/大小写重复拒绝、清洁解包篡改/额外文件拒绝。首次运行因过高文件数阈值误拒，按实际剔除缓存后的18,548项修正；哈希和106项要求未放松。未运行 Server 2025/Debian 13 或真实客户数据测试。

## 边界与下一步

本 ZIP 不是安装器：仍无 PostgreSQL18/pgvector 离线安装、正式 License/签名/密钥、服务账户/HTTPS、安装与升级脚本整合、完整 NOTICE/对应源码/法律复核、真实质量和发行 Gate；`release_eligible=false`。下一项单独在清洁目录运行 PDF/A-2b/中文 `--deskew` OCR 端到端，同时保持 JBIG TIFF 的安装/升级阻断。正式升级门禁另待真实服务/备份/静止证据。Debian 13 按用户现指示暂缓验证，但保留兼容目标。
