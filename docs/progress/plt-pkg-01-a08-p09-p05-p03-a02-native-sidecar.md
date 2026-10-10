# PLT-PKG-01-A08-P09-P05-P03-A02：Windows OCR 原生与模型非发行旁包

## 编码前检查

- 当前 Phase/WBS：Phase 2 / `PLT-PKG-01-A08-P09-P05-P03-A02`；只构建本机 Git 忽略的非发行 OCR 原生与模型旁包并清洁 ASCII 解包验证。
- 输入基线/前置：CR-PKG-001 官方 Tesseract5.5.3 安装资产/139 文件来源审计，Ghostscript10.08.0 官方安装资产/654 文件回读，固定 `tessdata_best` 四文件，P04-P02-P01 Paddle det/rec 10 文件模型旁包，P05-P02-A02 106-wheel 嵌入式 Python。
- 模块/实体/API/权限：仅新增旁包构建/回读工具和合成安全测试；不改 Parser 生产装配、实体、API、权限、Schema/Migration 或系统安装。
- 验收：每项输入先独立重新核源，归档不得有越界/重名/非 ASCII/链接，清单标明非发行及许可未审；新 ASCII 目录逐项 Hash；OCRmyPDF PDF/A-2b/`--deskew` 和 Paddle 图片/混合 PDF 均从解包模型/原生组件运行。
- 风险/回滚：完整 Tesseract 安装资产含 61 DLL/4 JAR，精确归属/NOTICE 尚不完整；Ghostscript AGPL 公开源码前置未满足。旧候选与安装均不覆盖；弃用新 Git 忽略旁包和新隔离目录即可回退。

## Windows 11 实测

- 新 `NOT-FOR-RELEASE-windows11-ocr-native.zip` 为 172,056,368 字节，SHA-256 `b1dadde7993cd7dca7d1a26d58b7322cca5e59f03bdb11a4a3712213a73ad24b`。构建前重新独立解包并逐项对照 Tesseract139/139、Ghostscript654/654；tessdata_best 4/4 与 Paddle 10/10 固定上游对象/指纹通过。归档 807 个载荷文件 + 1 manifest，逐项 Hash 回读，明确 `release_eligible=false`、`license_status=REVIEW_REQUIRED`。安全测试拒绝越界路径与冒充发行状态，2/2 PASS。
- 全新 ASCII 目录 `C:\Users\17231\AppData\Local\Temp\plm-ocr-native-reinstall-20261001` 解包后，807/807 文件 SHA-256 与 manifest 一致，808/808 条目数量一致。目录继承当前用户写权限，**不代表正式只读安装目标或服务账户 ACL**。
- 使用前一项嵌入式 Python3.13.15/106包，并仅通过本旁包解出的 Tesseract5.5.3、Ghostscript10.08.0 和 ASCII tessdata_best，合成表格 PDF 的 OCRmyPDF17.12.1 `--deskew`、PDF/A-2b 验证 exit0，预期中文/英数字术语 5/5。Paddle 两模型也仅从本旁包 ASCII 目录加载，合成 PNG 1 行及混合 PDF 原生 1/OCR 1 通过。无客户正文、Secret 或外部 AI 调用。

## 发行边界

旁包不是完整可用发行包：它未与 Web/后端/数据库/License/安装升级工具形成同一交付物；Tesseract Authenticode 未通过、传递 DLL/JAR 精确来源/许可缺项未解决，Ghostscript AGPL 对应公开源码与产品许可审查未完成，正式 ACL/服务账户、真实独立质量、Server2025/Debian13、完全断网安装与 Gate3～7 仍待。下一项应核对原生组件的最小运行依赖及许可证/Notice，并规划不扩大未审分发范围的正式集成；`release_eligible=false`。
