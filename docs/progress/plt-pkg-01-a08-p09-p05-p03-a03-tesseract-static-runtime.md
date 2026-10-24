# PLT-PKG-01-A08-P09-P05-P03-A03：Tesseract 静态 PE 运行子集

## 编码前检查

- 当前 Phase/WBS：Phase 2 / `PLT-PKG-01-A08-P09-P05-P03-A03`；只读计算官方 Tesseract5.5.3 CLI 的递归 AMD64 PE 导入图，并在隔离 ASCII 目录测试较小的运行子集。
- 输入基线/前置：CR-PKG-001 官方资产固定 Hash/139文件独立解包审计、P05-P03-A02 完整非发行旁包、106-wheel OCRmyPDF17.12.1 与 Ghostscript10.08.0。
- 模块/实体/API/权限：新增离线 PE 静态依赖审计工具与合成解析测试；不改 Parser 生产配置、实体、API、权限、Schema/Migration、正式安装或旧候选。
- 验收：PE import 表边界与 AMD64 校验、递归同目录依赖及外部 DLL 分类；隔离复制与来源 Hash；`--version`、`--list-langs`、四版面 PDF/A-2b/`--deskew` 术语回归。
- 风险/回滚：静态 import 表不覆盖延迟导入、`LoadLibrary`、插件和未测输入格式；缩减子集只是本机候选，不是许可范围或通用依赖证明。隔离目录可弃用，旧完整旁包不变。

## Windows 11 实测

官方 5.5.3 解包根目录的 `tesseract.exe` 递归导入图含 34 个本地二进制（exe 1、DLL 33），34/34 SHA-256 与完整官方解包目录一致。另有 22 个根目录 DLL 不在静态图中；安装器 `$PLUGINSDIR` 的 6 个 DLL 也不在此 CLI 静态图中。外部导入名 11 个（如 `kernel32.dll`、`ws2_32.dll`），仅按名字分类，不将其来源/目标机存在性视为已验。PE 解析合成递归正例、坏 PE 拒绝 2/2 PASS。

本机 Git 忽略报告为 `artifacts/package-prep/windows11/tesseract-static-pe-dependencies.json`。新 ASCII 目录 `C:\Users\17231\AppData\Local\Temp\plm-tesseract-min-pe-20261001` 仅含上述34二进制、官方 `configs`/`tessconfigs`/`pdf.ttf` 与固定4份 tessdata_best，共71文件；非训练数据配置/字体与官方资产逐项 Hash 相同，训练数据沿用 P05-P03-A02 固定值。Tesseract 报 `v5.5.3.20260724`、列出4语言。搭配106-wheel 嵌入式 Python及前项 Ghostscript，标准/密集/表格/轻微倾斜四版面全部 OCRmyPDF17.12.1 PDF/A-2b/`--deskew` exit0、五术语各5/5。

## 结论与边界

结果仅为 `STATIC_IMPORT_GRAPH_ONLY + FOUR_SYNTHETIC_LAYOUTS_PASS`。不能从这四页证明所有输入格式/动态依赖，也不能从“未被静态引用”推断其法律义务不存在。33个保留 DLL 的构建当次精确来源和许可证/NOTICE 仍需逐件闭合；Tesseract Authenticode 例外、真实质量、正式 ACL/Server2025/Debian13、AGPL和 Gate 仍未过，`release_eligible=false`。下一项对这33个候选 DLL 建立可追溯来源/许可矩阵；证据缺失则继续阻断正式发行而转向独立工作。
