# REQ-01-A03-P03-P01：Requirement 状态决策 Schema

日期：2026-10-07。结论：`REQ_01_A03_P03_P01_STATE_DECISION_SCHEMA_PASS`。下一项：
`REQ-01-A03-P03-P02` Requirement PATCH/DEFER/REJECT/ARCHIVE Owner。

## 实现与边界

- P03 拆为 P01 决策事实 Schema 与 P02 状态命令 Owner，避免在未验证数据形状时直接开放状态机；冻结
  API、角色和四状态不变。
- Migration0114 新增不可变 `req_requirement_state_decisions` 与
  `req_requirement_decision_evidence_refs`。DEFER/REJECT 决策固定 reason、impact、actor、前后版本，
  每个 Requirement/after_version 唯一；Evidence 通过子表保留，组合外键阻止决策归属漂移。
- P01 所有 INSERT/UPDATE/DELETE/TRUNCATE 均失败关闭；P02 将以同项目、PROJECT、ELIGIBLE Evidence
  现时证明替换关闭守卫。空历史可降0113，有历史拒降。

## 验证

- Windows 11 / PostgreSQL 18.6：0113→head→0113→head、两次drift、组合约束清单、Owner关闭、
  双表TRUNCATE拒绝和管理性历史fixture拒降通过，临时库清理。
- 定向14项、后端全量2974项通过，3项既有环境跳过；compileall通过。
- 开发wheel共1121项，SHA-256
  `2dd0b4dbc769270e79603e34eb27074e2c9d8e03e13aaa2a5f07650c9d73839c`，不是正式发行包。

无公开API、依赖、Secret、客户数据或外发变化；P02 Owner前不得写入决策表。
