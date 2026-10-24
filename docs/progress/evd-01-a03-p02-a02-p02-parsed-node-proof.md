# Evidence 解析节点精确定位内部证明

日期：2026-10-01。WBS：`EVD-01-A03-P02-A02-P02`。结论：`WINDOWS11_INTERNAL_PASS`。Evidence Application 现在可通过 Document 受权固定结果 Port 核对一个真实解析节点及其 Locator；这还不是正式 Evidence 创建或跨格式精度验收。

新 `ParsedNodeEvidenceProofService` 只接受与结果中唯一节点的来源定位完全相等的位置。`STRUCTURED_NODE` 还绑定 ParseRecordId 和 NodeId；直接位置遇多节点同位时拒绝。节点类型与 TEXT_RANGE、PAGE、PARAGRAPH、TABLE_CELL、SHEET_RANGE、SLIDE_SHAPE 的映射逐项检查，返回的正文指纹只取该节点原文。DOCUMENT 继续由原整文档证明处理；Parser 尚未生成独立 SECTION 节点，SECTION 直接失败关闭。结果 Hash、固定版本/源 SHA、重复节点 ID、畸形类型和上游撤权都被检查，不回传客户正文或物理路径。

验证：定向 7/7 单元 PASS，涵盖直接/结构化节点、类型映射、错误记录/节点、无位置/歧义、畸形结果和上游授权失败。隔离 PostgreSQL 18.6 测试从 Parser `ParsedResult.canonical_bytes()` 构造纯合成文本节点，存入真实 Document 私有结果文件和成功 ParseRecord，再经 Document 读取 Port 到 Evidence 节点证明；错误来源、失败记录、撤权及结果篡改均拒绝。测试簇停止并清理。Python 3.13 后端全量 1,743 项 OK（3 项既有环境跳过）；wheel 构建成功并包含新模块，SHA-256 `990bd6d397ac130e9b1b0eb7b02527d4f8d45230ff9a31d1d17f78c345e947ed`。

Changed：Evidence 内部证明模块、单元测试及隔离验证链。Migration、公开 API、ORM、权限和第三方依赖：无变化。兼容性：既有 DOCUMENT 证明保持原状；升级无需迁移；回滚为不装配新内部服务。已知问题：真实来源格式逐类位置复验、SECTION 位置、实际用户/License/运行账户组合、正式 Evidence 创建和目标平台发行仍未完成。下一项 `EVD-01-A03-P02-A02-P03` 应按真实格式逐类验证定位与可打开证据，不能将合成节点测试外推为 Gate 3 PASS。
