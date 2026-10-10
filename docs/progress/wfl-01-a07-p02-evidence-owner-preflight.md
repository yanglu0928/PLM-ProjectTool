# WFL-01-A07-P02：固定 Evidence Owner 前置核查

2026-10-02 / Phase 2 / `PRECONDITION_SPLIT`。输入为 P01 阻塞记录、冻结 `EVIDENCE_FIXED_PROJECT_V1` 与 Workflow Checklist/Stage Gate、现有 Evidence 资格/Viewer 和 Document/ParseResult 受权 Port。只读核查发现：EligibilityRepository 可锁 Evidence 身份/资格/版本但不含 locator/固定 ParseRecord；Document `get_source_facts_for_evidence` 可同事务证明类别/版本，但现有 ParsedNode 与文件 Viewer 是独立事务/存储过程；普通 GLOBAL Evidence/Document 读取只授 DeploymentAdmin，与 Workflow PM 引用标准来源的冻结语义不一致。因而本项不以当前 Port 冒充完整 Owner、不接 Checklist 写入口。

偏差、安全授权、方案比较、迁移/回滚与验证计划先登记在 [CR-WFL-005](../changes/CR-WFL-005-fixed-evidence-owner-boundary.md)。选择内部窄引用证明而非开放 GLOBAL 浏览/下载；后续先做 Document 固定 ParseRecord/制品同事务证明，再做 Evidence Owner 与 Workflow 接线。无本项产品代码、Schema、API 或依赖变更；测试为源码和冻结设计静态核查，**未运行**新业务矩阵，不能标记实现 PASS。Review Subject/ApprovedException Owner、正式信任、浏览器、三平台、质量/UAT/Gate仍开放。
