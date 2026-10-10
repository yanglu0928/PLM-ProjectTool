# WFL-01-A07-P07-A02：Workflow Checklist 不可变记录追加

日期：2026-10-05。结论：`WFL_01_A07_P07_A02_CHECKLIST_APPEND_PASS`。

## 完成范围

- 新增调用方事务内的 `SqlAlchemyChecklistRecordAppendRepository`，固定按 `Workflow → 当前 Stage → ChecklistItem → 当前不可变记录` 持锁；Repository 不授权、不审计、不提交事务。
- 首次写入只接受 `PENDING/v0/no supersedes`，后续更正必须引用精确上一条记录，禁止已有历史退回 `PENDING` 或形成分叉。
- 原子写入 Record/Refs，并将 Item 状态、Item lock version、Workflow lock version 各推进一次；调用方不提交时全部回滚。
- 记录摘要绑定 Record 全字段、Stage 当前观测及按 `ref_kind/ref_id` 规范排序的最小证明观测；当前记录读取会重新计算摘要，存储内容被篡改时失败关闭。
- 本项只提供通用持久化能力，不接 Session/CSRF/权限/License、Handover资格Owner、幂等、Audit或HTTP；这些边界留给 `P07-A03`。

## 兼容、偏差与回滚

- 无Schema/Migration、冻结 `/api/v1`、角色、依赖、配置、Secret、客户数据或外发变化；沿用已冻结的0030/0032结构。
- 读取侧新增摘要复算属于既有不可变记录完整性收紧：历史中若存在无法由已存Record/Refs重算出的占位摘要，将不再被信任。当前正式写链此前尚未开放，因此不涉及生产数据迁移；验证脚本的合成旧占位记录不能作为正式可读记录。
- 回滚可删除新增追加Repository并撤销读取侧摘要复算；已写Record为不可变审计事实，不以删除或改写历史作为回滚手段。

## 验证证据

- 单元定向：11项通过，覆盖锁形状、首条/更正链、规范化/重复Refs、摘要绑定Stage和证明观测、当前记录原有失败关闭合同。
- Workflow相关回归：104项通过。
- 后端全量：2737项运行、3项按既有条件跳过，0失败。
- 开发wheel包含三项新增模块，SHA-256 `7a2a0d35b178ee416db473c731039212f19604d26e95a4780964f3457b2d52e0`；仅为开发验证产物，不是可发行程序包。
- Windows 11 / PostgreSQL 18.6 实库：空库迁移与Alembic check；首次PASS、FAIL更正、精确Evidence/Review观测、调用方未提交回滚、三层当前事实锁、双写者串行化（1成功/1 `CONFLICT_VERSION`）、伪造Evidence观测由数据库拒绝、测试注入摘要损坏由读取侧拒绝，全部通过。
- 旧 `WFL-01-A05-P04` 当前记录实库回归改用生产摘要后重新通过，证明读取完整性收紧未破坏合法链。
- ReviewRound身份在本项实库验证中为合成事实；不宣称真实Handover授权、人工批准、Audit、Gate或公开API通过。

下一项：`WFL-01-A07-P07-A03` 受权命令与Handover策略注册。
