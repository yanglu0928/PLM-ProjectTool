# Office 文档来源位置复验

日期：2026-10-01。WBS：`EVD-01-A03-P02-A02-P03-P02`。结论：`WINDOWS11_SYNTHETIC_FORMAT_PASS`。临时目录中的纯合成 DOCX、PPTX、XLSX 文件已由正式 Parser 从实际文件字节解析，再用独立 Office 读取库按定位回查文本，最终经 Evidence 节点证明接受。

DOCX 的两个正文段落和两个表格单元格可分别按段落序号、表号/行/列回查。PPTX 的文本形状和表格单元格可按页码、ShapeId、表格行列回查。XLSX 的中文命名工作表 B2 和公式 C3 可按 Sheet/A1 地址回查；公式作为文本 `=1+1`，未执行计算。三类源节点均通过直接 Locator 和绑定 ParseRecordId/NodeId 的 STRUCTURED_NODE 证明，节点正文 SHA 与证明指纹一致。

验证脚本退出 0，临时文件自动清理；现有 Office 解析器定向 6/6 单元测试通过。本项未修改生产代码、公开 API、ORM/Schema、权限或第三方依赖；Migration 和升级动作均无。此前后端全量 1,744 项及 wheel 验证仍是上一 WBS 的结果，本项未重复全量构建。已知问题：Python Office 读取库可打开不等于 Microsoft Office GUI 验收，复杂合并单元格、图片/流程、多层表格、PDF/OCR、真实客户资料、正式账户组合与 Gate 3 仍未验证。下一项单列 PDF 文本/OCR/图片定位。
