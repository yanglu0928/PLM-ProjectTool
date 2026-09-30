# PLT-PKG-01-A08-P09-P03-P03-P02：Tesseract 官方 Windows 包原生/JAR 许可缺项清单

## 编码前检查

- Phase/WBS：Phase 2 / PLT-PKG-01-A08-P09-P03-P03-P02，仅审计固定官方 5.5.3 NSIS 解包字节与包内许可材料，不给法律结论。
- 基线/前置：CR-PKG-001、P03-P01 官方 Release digest、P03-P02 AMD64 CLI/合成 OCR；本项使用全新只读解包目录，不复用含测试 PNG 的目录。
- 模块/实体/API/权限：打包审计工具；无产品实体、API、权限、DB/Migration 或运行装配变化。
- 验收：压缩包完整性测试、全新提取 139 文件数量、61 DLL/4 JAR 逐文件 Hash、包内 LICENSE/NOTICE 路径扫描、篡改/清单差异拒绝；明确未知许可。
- 风险/回滚：精确来源 Hash 不等于所有文件再发行权；审计 JSON 在 Git 忽略目录，可撤新工具/忽略目录，不改历史安装包。

## 结果

本机 7-Zip 对 SHA-256 `bee9e3434bd94fd65387d9be28cd467a41f61b1275383b55b0f59a1331270ae4` 的官方 NSIS 文件 `t` 完整性检查和新目录 `x` 提取均 PASS。新增审计工具又在临时目录独立解包一次，对 139 文件的路径与 SHA-256 逐项比较并留证，识别 61 DLL、4 JAR；包内独立 LICENSE/NOTICE 路径仅 `doc/LICENSE`（Apache 2.0，固定 Hash）。四个 JAR 中仅 `jaxb-api-2.3.1.jar` 内含 `META-INF/LICENSE.txt`，`piccolo2d-core`、`piccolo2d-extras`、`ScrollView` 均未检出内嵌 LICENSE/NOTICE。61 DLL 未发现各自随附的独立许可/通知文件；这只是当前安装资产的清单结果，不推断它们没有上游许可证。

本地 Git 忽略的 `artifacts/package-prep/windows11/tesseract-5.5.3-payload-inventory.json` 保存 139 项路径/大小/SHA-256。合成单元正例、安装包坏 Hash、单 DLL 篡改与额外文件拒绝 PASS（1 个测试方法、4 类断言）；`release_eligible=false`。后续须将每个 DLL/JAR 映射至准确上游版本及许可证，取得所需许可原文/NOTICE 与再发行义务，再与正式发行包一同提供；包内顶层 Apache 文本不能代替传递组件清单。签名异常、独立 OCR 质量、正式目标账户/Server2025 与 Gate 仍未通过。
