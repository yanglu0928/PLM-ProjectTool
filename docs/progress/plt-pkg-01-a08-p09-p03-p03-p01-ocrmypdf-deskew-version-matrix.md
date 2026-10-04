# PLT-PKG-01-A08-P09-P03-P03-P01：Tesseract 5.5.3 与 OCRmyPDF deskew 对照

## 编码前检查

- Phase/WBS：Phase 2 / PLT-PKG-01-A08-P09-P03-P03-P01，仅定位 Windows11 官方 Tesseract 升级后的路径/质量差异。
- 基线/前置：CR-PKG-001 已在替换前登记；POC-01 5.4/PSM6/五术语 PASS，OCRmyPDF17.12.1、Ghostscript10.08、固定 tessdata_best 及合成验收脚本。
- 模块/实体/API/权限：只给 PoC 验证脚本添加可选 PSM，默认值仍为 6；无产品 Parser、实体、API、权限、Migration 或生产配置变化。
- 验收：相同字体/合成 PDF/数据/配置/运行时条件下复验 PDF/A-2b、deskew、中文 Windows 编码及五术语；失败及配置依赖明确留证。
- 风险/回滚：单页合成样本不足以决定默认 PSM 或广义质量；撤可选 CLI 参数即可回滚，旧证据及输入不变。

## 失败链与受控对照

1. 5.5.3 exe 与 `tessdata_best` 都位于中文仓库绝对路径时，OCRmyPDF 语言探测触发 `filesystem error: Cannot convert character sequence: Illegal byte sequence`，exit 3。
2. 只将四份 `.traineddata` 放入 ASCII 目录后，`--list-langs` 4/4 正常，但 OCRmyPDF 报缺 `hocr` 配置，exit 9。再补官方 5.5.3 安装包自带 `configs`、`tessconfigs`、`pdf.ttf` 后，链路可运行。此处说明 OCR 离线安装必须包含运行配置，不能只带模型参数。
3. 完整 ASCII tessdata/配置、固定合成 PDF 与 OCRmyPDF17.12.1/Ghostscript10.08 下：

|Tesseract|PSM|OCRmyPDF|PDF/A-2b|deskew|五术语|结论|
|---|---:|---:|---|---|---:|---|
|本机 5.4.0.20240606|6（原默认）|exit 0|PASS|PASS|5/5|旧 PoC 控制样本通过|
|官方解包 5.5.3.20260724|6（原默认）|exit 0|PASS|PASS|4/5|“工具”被识别为“工只”，质量回退|
|官方解包 5.5.3.20260724|3|exit 0|PASS|PASS|5/5|仅此样本候选通过|
|官方解包 5.5.3.20260724|4|exit 0|PASS|PASS|5/5|仅此样本候选通过|
|官方解包 5.5.3.20260724|11|exit 0|PASS|PASS|4/5|未达门槛|

测试使用仓库既有合成 PDF 验证脚本及新 Git 忽略输出目录；不外发客户数据。PoC CLI 新增 `--tesseract-pagesegmode {3,4,6,11}`，省略时仍为 6，默认值修改后的 5.4 回归 5/5 PASS。5.5.3 的四组 `--deskew` 与 PDF/A-2b 执行均无先前 Windows 输出解码异常，但只证明该环境与样本。独立版面、真实扫描质量、第三方许可、签名例外、目标账户/Server2025 与发行包尚未验；不得直接将 PSM 改为 3/4 或宣称 5.5.3 质量 PASS，`release_eligible=false`。
