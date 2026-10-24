# PLT-PKG-01-A08-P09-P04-P01：Windows OCR 独立合成版面对照

## 编码前检查

- Phase/WBS：Phase 2 / PLT-PKG-01-A08-P09-P04-P01；仅扩大 PoC 合成 PDF 版面以比较固定版本/PSM，不改生产 OCR 配置。
- 基线/前置：CR-PKG-001 已登记 5.5.3 签名、中文路径和单页质量差异；POC-01 固定 OCRmyPDF17.12.1/Ghostscript10.08/tessdata_best/五术语；P03-P03-P01 有同页对照。
- 模块/实体/API/权限：只改 PoC 验证脚本的可选合成版面；无产品 Parser、实体、API、权限、Schema/Migration 变化。
- 验收：标准、密集、表格、轻微倾斜四种版面，同页不同版本/PSM 的渲染像素一致；逐组看 OCRmyPDF exit、PDF/A-2b、deskew、五术语，默认旧脚本行为回归。
- 风险/回滚：合成样本不是客户扫描件或 POC-03 独立质量集；撤可选 `--layout` 即回滚，不覆盖旧 PoC 输出。

## 结果（Windows 11）

验证器新增 `--layout {standard,dense,table,skewed}`，省略仍为原 `standard`。各版面不同版本/PSM 生成的 PDF 元数据字节不全相同，但渲染后的页面像素 SHA-256 在同版面内唯一，证明 OCR 输入图像相同。所有下表运行均采用相同 ASCII tessdata_best+官方 configs、OCRmyPDF17.12.1、Ghostscript10.08.0、PDF/A-2b 与 `--deskew`；OCRmyPDF exit 0、PDF/A 验证 PASS。

|版面|5.4/PSM6|5.4/PSM3|5.5.3/PSM6|5.5.3/PSM4|5.5.3/PSM3|
|---|---:|---:|---:|---:|---:|
|标准|5/5|未运行|4/5|5/5|5/5|
|密集|4/5|5/5|4/5|5/5|5/5|
|表格|1/5|4/5|1/5|4/5|5/5|
|轻微倾斜|5/5|5/5|5/5|5/5|5/5|

旧版 5.4/PSM6 的 `standard` 默认参数在新增 `--layout` 后重新运行仍 5/5 PASS。当前**推荐 5.5.3/PSM3 进入后续候选评估**（四种合成版面 20/20 术语），但这不替代独立真实扫描质量、低质图/字体/表格复杂度或人工标签；未修改 PoC 默认 PSM6，也未接入产品配置。5.5.3/PSM6 和 5.4/PSM6 在表格均失败，不能用单个旧样本作版本质量结论。

所有输入和报告位于 Git 忽略的 `artifacts/package-prep/windows11/tesseract-layout-*`，无客户正文外发。原生依赖精确许可、无效 Authenticode 的替代控制、正式只读 ACL/Windows Server2025、OCRmyPDF 离线包和 Gate 均待，`release_eligible=false`。
