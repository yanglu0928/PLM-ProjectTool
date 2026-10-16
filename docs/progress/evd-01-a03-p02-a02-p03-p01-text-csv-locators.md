# 纯文本与 CSV 来源位置复验

日期：2026-10-01。WBS：`EVD-01-A03-P02-A02-P03-P01`。结论：`WINDOWS11_SYNTHETIC_FORMAT_PASS`。本项用临时目录中实际落盘的纯合成 TXT/CSV 文件，验证 Parser 输出的位置可回查源内容，并由 Evidence 节点证明接受；不读取、外发或提交客户文件。

TXT 样本覆盖 UTF-8 BOM、中文与 CRLF。Parser 规范化后两个节点的起止字符区间可切回相同文本，位置指纹等于切片 SHA-256；直接 Locator 与带 ParseRecordId/NodeId 的 STRUCTURED_NODE 均匹配。CSV 样本覆盖中文、引号内跨行及空单元格，6 个节点的单元格地址与独立 `csv.reader` 读取的行列一致。非空节点可定位，空单元格不得成为 Evidence，但不使邻近非空节点失效。文件在固定元数据后被改动，Parser 返回 `FILE_INTEGRITY_MISMATCH`。

实施中修正 Evidence 节点验证：仅要求节点文本为字符串，允许结果保留空 CSV 单元格，但选中节点必须非空；同时限定各 Parser Profile 可以出现的节点类型，防止跨格式伪装。定向节点证明 8/8、临时文件验证退出 0、Python 3.13 后端全量 1,744 项 OK（3 项既有环境跳过）；wheel 构建成功，SHA-256 `e37aa1b3bb85915c5b5a5bd16f61a09aa33140e96a4a56624dc2dead48f8dc71`。

Changed：Evidence 内部节点边界、单元测试和格式验证脚本。Migration、公开 API、ORM、权限及依赖：无变化。兼容性：旧 DOCUMENT 证明不变；升级无迁移；回滚可停用新内部证明服务。已知问题：本项只覆盖合成 TXT/CSV，不证明客户文件、DOCX/PPTX/XLSX、PDF/OCR、真实用户/License 组合或完整 Gate。下一项 `EVD-01-A03-P02-A02-P03-P02` 对 Office 三格式逐一复验实际位置。
