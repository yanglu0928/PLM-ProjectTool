# REQ-01-A05-A03：PROJECT Evidence 与 Capability 固定来源证明

日期：2026-10-07。结论：`REQ_01_A05_A03_REFERENCE_SOURCE_PROOFS_PASS`。下一项：
`REQ-01-A05-A04` Human Decision证明与A05五类闭环。

## 实现与边界

- Evidence 模块新增 Requirement 专用最小 proof，复用既有固定来源仓储在调用方事务内共享锁读取精确
  `PROJECT / 同Project / ELIGIBLE` 行；返回Evidence、固定Document/Version、lock version与隐藏指纹，
  不向Requirement复制locator、excerpt、路径或Document正文。
- Capability 模块新增 Requirement 专用最小 proof，只接受ACTIVE GLOBAL Baseline当前指针精确指向的
  APPROVED Version与其中AVAILABLE稳定Item；同时绑定`CAP-01 / DEPLOYMENT_ALL_V1`的GLOBAL APPROVED
  Review、Round和同Baseline/Version/内容指纹的Review Snapshot。
- Capability按`baseline_version_id + capability_item_id`证明冻结Assessment引用，不按时间选择latest，
  不接受旧批准Version、不可用Item或仅有状态列而无精确审批快照的记录。
- 两个adapter均零写、不自行commit、不做项目权限或License替代校验；这些仍由A06调用方Owner负责。

## 验证

- Windows 11 / PostgreSQL 18.6：PROJECT/ELIGIBLE Evidence、当前GLOBAL Capability正式审批链、跨项目、
  错Item、Evidence撤销、Review Snapshot指纹漂移及proof零写通过；Alembic drift无新增操作。
- 定向16项、后端全量2990项通过且3项既有环境跳过；开发wheel共1135项，SHA-256
  `e305a87de745b8d7e83671f29279b20e22207672b5b9a8a2b9f4b062f6e208a4`，不是正式发行包。

无Schema、Migration、公开API、依赖、Secret、客户数据或外发变化；A04、A06～A12、Gate3/UAT/发行待。
