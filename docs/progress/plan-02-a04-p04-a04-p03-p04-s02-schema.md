# PLAN-02-A04-P04-A04-P03-P04-S02：PlanVersion 快照 Schema 第一片

日期：2026-10-26。结果：`PASS_SCOPE_LIMITED`。仅增量 Schema；PlanVersion 业务写口仍关闭。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PLAN-02-A04-P04-A04-P03-P04-S02`|
|输入基线|Gate 2 冻结 DM-05/API-04（原提交 `64cdf09` 不改写）；CR-PLAN-002 方案 C；S01字段映射；Schema head `20261024_0185`|
|前置任务|S01字段映射完成；当前 Plan/Version/WBS 为关闭式 Schema，完整快照写 Owner 不存在|
|涉及模块/实体|Plan ORM 与 Migration；PlanVersion、WbsItem、ProjectMember、固定排除目标及 owned child rows|
|涉及 API / 权限|无 API 或授权变化；不开放 PlanVersion CREATE，不写业务行|
|验收标准|强类型增量 ORM/Migration；新增历史触发器与降级保护；PostgreSQL 18.6 up/down/re-up、drift；定向及完整后端回归|
|风险|错误枚举会将未冻结的业务白名单写死；旧业务快照不得被虚构回填；OutputArtifact 缺 Owner；不允许用 Schema PASS 推断端到端写链通过|

## Changed

- Migration `20261026_0186` 在 `20261024_0185` 后追加 `calendar_ref`、WBS 分类/成员归属/日期工期/风险/排除字段，以及版本排除、WBS协作角色、进入/验收条件三类 typed child 表。
- 使用 ProjectMember 与版本/来源的复合外键、目标类型互斥 CHECK、有序唯一约束、字段长度/日期/时长约束；新增 child 表在业务 Owner 未安装时通过触发器拒绝写入，并拒绝 TRUNCATE。
- 空新增字段保持 NULL，不回填虚构业务事实。非空 `output_refs` 仍须由后续写 Owner 失败关闭，因为 OutputArtifact 目标不存在。
- 复核发现冻结 DM-05 只定义“协作角色”语义、未固定枚举；因此没有把现有项目成员角色误当作完整白名单，数据库只校验 role code 形状，具体允许值留给后续 Plan Owner 受控 registry。属于本片实施中的收敛修正，不改变冻结 API 或业务语义。

## Migration 与测试

- Windows 11 本机 PostgreSQL 18.6 新建隔离库：先升至 0185，再升 head、降回 0185、重升 head；Alembic `command.check` 报告 `No new upgrade operations detected`。结果：`PLAN_SCHEMA_0186_UP_DOWN_REUP_AND_DRIFT_PASS`。
- Alembic drift 检查有既存向量表达式运算符类及 computed-default 比较警告；未检测到新 upgrade operations。这些告警不属于本 WBS 变更。
- 定向 Schema/Migration/metadata 测试：10 passed。
- 最终代码状态完整后端回归：4110 passed、3 skipped、6153 subtests passed。
- 本片数据库来自空业务库的迁移链，未构造既有 Plan/PlanVersion 行，也未对新增复合引用进行真实 PG 负例注入；因此结果限定为 `PASS_SCOPE_LIMITED`，不得记作完整有数据迁移验收。
- 一次隐藏进程启动封装返回失败，但 PostgreSQL 记录无服务错误；使用直接受控 `pg_ctl` 启动后迁移验收成功。临时验证目录保留在本机 Temp（环境删除策略拒绝递归清理），数据库已正常停止，不含客户数据。

## Files / Migration / API

- ORM：`apps/backend/src/plm_assistant/modules/plan/infrastructure/orm.py`
- Migration：`apps/backend/src/plm_assistant/migrations/versions/20261026_0186_plan_version_snapshot_fields.py`
- Tests：`apps/backend/tests/unit/test_plan_version_snapshot_schema.py`、migration head 与 ORM metadata 断言。
- API：无变化；未安装 PlanVersion 业务写 Owner。

## Known issues / Next

- 尚未验证含真实既有 Plan/PlanVersion 历史行的升级，也未验证新增 FK 的 PostgreSQL 负例；历史损坏守卫只以空库升降重升和 schema/unit 检查覆盖。
- PlanVersion aggregate 创建、来源锁定/复查、幂等、Audit、条件/角色/类别白名单、Calendar resolver、OutputArtifact 引用、Review、HTTP/UI 均未由本片实现或验收。
- Next：`PLAN-02-A04-P04-A04-P03-P04-S03`，先完成编码前核查并实现受控 PlanVersion DRAFT 聚合写 Owner，使用 0186 字段、在事务内固定/复核来源；在接口仍关闭前覆盖真实 PostgreSQL 负例。Pilot、Gate 3 与正式 Release 状态不变。
