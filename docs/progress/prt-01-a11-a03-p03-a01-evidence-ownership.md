# PRT-01-A11-A03-P03-A01：聚合受审主体 Evidence 归属兼容修订

日期：2026-10-08。状态：内部契约验证通过；Prototype Workflow Owner 未完成，资格入口未开放。

编码前检查：Phase 2/Gate 2 冻结基线、`CR-PRT-005`、A11-A03-P01/P02 锁定输入及 Workflow 现有聚合 DTO/Checklist 写时证明已核对。发现现有聚合要求每个受审主体都有 Evidence，但 `PRT-03` 正式主体依据为 DocumentVersion 制品、Review 与 Trace，不能假装其拥有 Requirement 来源 Evidence。已先补充 `CR-PRT-005` 兼容修订与回滚/验证方案，再修改内部通用聚合 DTO；不改已冻结 `/api/v1`、Schema、权限或业务写操作。

修订仅允许聚合中单个主体的 Evidence 集为空；聚合整体仍必须含真实 Evidence，现有单主体资格合同的非空约束不变。后续 Prototype Owner 必须把 Requirement 的真实来源 Evidence 绑定到 Requirement 主体或范围级证据，PRT-03 以真实 Review/制品/Trace 另行证明，不用 Evidence 字段伪造归属。受权 Registry、写时重新资格验证与 Review Basis 记录仍沿用既有机制。

验证：新增混合 REQ-03/PRT-03 及零总 Evidence 拒绝两项；聚合定向 6 项/7 子例，后端全量 3224 项通过、3 项条件跳过、4791 子例通过。无 PostgreSQL/HTTP 或 Prototype Owner PASS 结论。风险与回滚见 `CR-PRT-005` 修订节。
