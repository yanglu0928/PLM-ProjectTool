# POC-05 测试样本检查

|样本|检查方式|结果|
|---|---|---|
|DOCX|OOXML 结构、统一解析、显式分页和表格断言|PASS；当前工作区依赖无打包 LibreOffice，未完成 DOCX 转 PNG|
|PPTX|Artifact Tool finalizer、原生表格检查、逐页 PNG 目视检查|PASS|
|XLSX|Artifact Tool inspect、错误扫描、两个工作表逐表 PNG 目视检查|PASS|
|文本 PDF|两页 150 DPI PNG 逐页检查|PASS|
|扫描 PDF|150 DPI PNG 检查；保留轻微倾斜、噪声和对比度衰减|PASS|
|CSV|UTF-8 BOM、三行结构和统一解析断言|PASS|

PNG、PPTX finalizer receipt 和 DOCX 渲染失败日志属于运行期 QA 中间文件，保存在被 Git 忽略的 `artifacts/poc-05/qa/`。
