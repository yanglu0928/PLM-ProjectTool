# 文本型 PDF 来源位置复验

日期：2026-10-01。WBS：`EVD-01-A03-P02-A02-P03-P03-P01`。结论：`WINDOWS11_SYNTHETIC_NATIVE_PDF_PASS`，仅适用于带原生可提取文本的合成 PDF。

验证脚本在临时目录创建并落盘两页 PDF。正式 Parser 从文件字节产生三个 `PDF_TEXT_LINE` 节点；独立重新打开该文件后，在相同 PyMuPDF 版本的排序文本视图中按每个节点的页码和规范字符区间回查正文及 SHA-256 指纹。三节点均经 Evidence 直接 Locator 与绑定 ParseRecordId/NodeId 的 STRUCTURED_NODE 证明接受。源字节被改动后返回 `FILE_INTEGRITY_MISMATCH`；含空白页的另一份 PDF 返回 `PARSER_OCR_REQUIRED`，没有以部分文本冒充完整解析成功。

验证脚本退出 0，原 PDF 解析定向单元测试 3/3，临时文件自动清理。本项仅增验证与文档，不改生产代码、公开 API、ORM/Schema、权限、依赖或发行包；无迁移和升级动作。前项后端全量测试与 wheel 结果不在本项重计。

已知边界：回查依赖相同 PyMuPDF 文本视图；复杂字体/布局、扫描 PDF、图片 OCR、实际模型文字及坐标准确度、客户材料、正式账户组合与 Gate 3 均未通过。下一项分别验证扫描 PDF/图片的坐标契约，并独立判断是否具备真实离线 OCR 模型运行条件。
