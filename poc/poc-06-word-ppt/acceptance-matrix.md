# POC-06 验收矩阵

|ID|验收项|Windows 11|Windows Server 2025|Debian 13|证据要求|
|---|---|---|---|---|---|
|P06-A01|环境与 Office 版本采集|PASS|PASS_NO_OFFICE|NOT_RUN|脱敏环境 JSON|
|P06-A02|100 页 DOCX 确定性生成|PASS|PARTIAL_PACKAGE_PASS|NOT_RUN|页数、Hash、包完整性|
|P06-A03|DOCX 中文与三级章节|PASS|NOT_RUN|NOT_RUN|标题层级与中文断言|
|P06-A04|DOCX 表格、图片与流程|PASS|PARTIAL_PACKAGE_PASS|NOT_RUN|对象数量与来源断言|
|P06-A05|50 页 PPTX 确定性生成|PASS|PARTIAL_PACKAGE_PASS|NOT_RUN|页数、Hash、包完整性|
|P06-A06|PPTX 中文与章节结构|PASS|NOT_RUN|NOT_RUN|标题与章节断言|
|P06-A07|PPTX 原生表格、图片、流程与数据图|PASS|NOT_RUN|NOT_RUN|可编辑对象断言|
|P06-A08|Microsoft Word 正常打开|PASS|BLOCKED_NO_OFFICE|NOT_RUN|COM 只读打开与 PDF 导出|
|P06-A09|Microsoft PowerPoint 正常打开|PASS|BLOCKED_NO_OFFICE|NOT_RUN|COM 只读打开与 PDF 导出|
|P06-A10|DOCX 100 页全量视觉检查|PASS|NOT_RUN|NOT_RUN|100 张 PNG、无裁切/重叠/缺字|
|P06-A11|PPTX 50 页全量视觉检查|PASS|NOT_RUN|NOT_RUN|50 张 PNG、无裁切/重叠/缺字|
|P06-A12|隐私与仓库安全|PASS|PASS|NOT_RUN|无客户资料、Secret 或运行日志|

## 当前验收阈值

- Word 在 Microsoft Office 中计算页数必须恰好为 100，PowerPoint 幻灯片数必须恰好为 50。
- 两个文件必须正常打开、可导出 PDF、OOXML 包完整且不得出现修复提示。
- 中文、多级章节、表格、图片和流程必须在对应文件中均有覆盖。
- 原生表格、流程和数据图不得用整页截图替代。
- 视觉检查必须覆盖全部 100 个 Word 页面和 50 个 PPT 页面。
