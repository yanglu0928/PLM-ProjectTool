# SOL-06-A16-P03：Review List 索引迁移

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`REVIEW_LIST_INDEXES_PASS`；本项只完成 Migration 0166 与 ORM 索引，不表示 Repository、HTTP、Windows Inbox 或 Gate/Pilot 已通过。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-06-A16-P03`|
|输入基线|冻结 REVIEW_LIST、`CR-RVW-004`、A16-P02 稳定顺序与 `my_pending` 合同|
|前置任务|P02 DTO/加密游标已通过；新增索引不依赖未实现的 Repository/Router|
|涉及模块|Review ORM、Alembic Migration、Schema 合同测试与一次性数据库验收|
|涉及实体|`rvw_reviews`、`rvw_review_assignments`；不改变 Review/Round/Assignment 业务事实|
|涉及 API|无运行 API 变化|
|涉及权限|无策略变化；索引不能代替 Session、Project、Subject Owner 或 Assignment 当前事实检查|
|验收标准|空库和有历史升降重升、行数不变、索引定义/查询计划、ORM parity、Alembic drift、全量回归与 wheel 入包|
|风险|错误排序导致 keyset 漏重；全 Assignment 索引膨胀；把索引命中误述为授权或性能验收|

## 实施结果

- 新增 `20261019_0166`，父版本为 `0165`。`ix_rvw_reviews__scope_created(scope, scope_project_key, created_at DESC, review_id DESC)` 与 P02 keyset 位置完全一致。
- 新增 partial index `ix_rvw_assignments__reviewer_pending(scope, scope_project_key, reviewer_id, review_round_id) WHERE assignment_state='PENDING'`，只覆盖 Reviewer Inbox 当前候选，不为已决定历史扩大索引。
- ORM 声明同名、同序、同 predicate；迁移不增列、不回填、不改行。降级只删除两个索引，因此可在保留 Review 历史的情况下回到 0165，但应用入口必须先关闭或回退。
- 新增独立 Windows 验收脚本，拒绝占用中的 55432，仅在既有 ASCII 临时根创建自有 PostgreSQL 18.6 集群；退出时停止实例并只删除自建目录。

## 验证证据

- 定向迁移/ORM：`9 passed`。首次失败仅为测试误假设 SQLAlchemy 降序表达式字符串带表名前缀；按实际稳定表达修正测试后通过，索引列与方向未变。
- Windows 11 / PostgreSQL 18.6：空库 up/down/re-up；在 0165 生成 24 条有效 Review、Round、PENDING Assignment 后升级、降级、重升；三表行数始终 `24/24/24`，两个 `pg_indexes` 定义准确，关闭顺序扫描后两条目标 SQL 的实际计划分别命中新索引，`alembic check` 无新操作。一次性数据库、集群和目录均已清理。
- Alembic 保留既有 HNSW 表达式与 computed default 比较告警；没有新增 drift，未把告警静默当成失败或清除旧技术债。
- 后端全量：`3765 passed, 3 skipped, 5870 subtests passed`。
- Python 3.13 开发 wheel：1419 项，Migration 与 ORM 均入包，SHA-256 `9774c762df07e8e4ce8ca31560d0a9432b091ab21c0405d6fa0e0dbd0cb2f6d3`；不是 Pilot/Release 包。

## 兼容、升级、回滚与未完成项

- 升级前按既有数据库流程备份并执行至 0166；无数据转换或停写语义变化。大量生产历史下建索引的锁与耗时仍需正式性能/升级窗口验证，本次 24 条合成历史不构成规模性能结论。
- 回滚先关闭尚未实现的 LIST 入口，再降至 0165；Review/Assignment/Decision 历史不删除。冻结 REVIEW_GET/DECIDE、角色、License、依赖和响应均不变。
- Repository、逐项 Subject Owner 授权、Project `REVIEW_LIST` policy、HTTP、Windows Vault key/组合、前端与 Edge 尚未完成；Gate 3、Pilot 和正式发行状态不变。

Next：`SOL-06-A16-P04` 实现只读候选 Repository、Project `REVIEW_LIST` 授权及逐项 Subject Owner 过滤的 `all/my_pending` Application Service；保持短页继续语义，不提前挂 HTTP。
