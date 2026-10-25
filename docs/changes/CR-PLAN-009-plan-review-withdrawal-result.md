# CR-PLAN-009：Plan Review 撤回终态事实

- 日期：2026-10-26
- 状态：`AUTHORIZED_FOR_IMPLEMENTATION_BY_CONTINUOUS_USER_AUTHORIZATION`
- 发现于：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P02` 编码前检查
- 基线：Gate 2 冻结模型/API；CR-PLAN-007 的 Migration 0190；CR-PLAN-008 的 Migration 0200。

## 差异与影响

Review 统一状态机允许已开始的 PROJECT Review 被项目负责人撤回，Review/Round 最终成为 `WITHDRAWN`。PlanVersion 0190 仅为 `APPROVED`、`RETURNED`、`SUPERSEDED` 建立不可变结果；其 `RETURNED` 结果触发器要求对应 Review 和 Round 真实为 `RETURNED`。因此不能将撤回伪记成 Review 退回，也不能在无 Plan 结果事件时提交终态回调；否则会失败回滚或将 PlanVersion 留在 `IN_REVIEW` 且无法再次送审。

CR-PLAN-007 已明确撤回/取消新跃迁必须独立核验。本 CR 补齐这一最小缺口。

## 方案与决定

- A：拒绝 Plan Review 撤回。拒绝：与统一 Review 可用状态机产生不一致；一旦 Review 允许撤回，将留下不可继续的 `IN_REVIEW` PlanVersion。
- B：将 Review 撤回伪记成 `RETURNED`。拒绝：伪造业务事实，且0190会正确拒绝，因为真实 Review/Round 是 `WITHDRAWN`。
- C（选择）：追加 Migration `20261026_0210`，扩展 PlanVersion 生命周期结果表允许内部 `WITHDRAWN` 事件；它表示 `IN_REVIEW → RETURNED` 的 PlanVersion 处置结果，但必须绑定真实终态 `WITHDRAWN` Review/Round 与事件 Actor。公开 PlanVersion 状态保持现有 `RETURNED`，不改冻结 API或Review状态图。0190历史迁移不改写。

## 实施与验证要求

- 先实现并测试 0210：将事件表精确加入 `WITHDRAWN` 结果形状；事件插入必须证明真实 PROJECT Review/Round=`WITHDRAWN`、当前Round、Subject固定Version及匹配 Actor 终态事件；PlanVersion 更新仍须有同事务结果事件；保持结果 UPDATE/DELETE/TRUNCATE 关闭。
- migration 应检查已有PlanVersion绑定的Review是否已被撤回；发现此种既存状态而无法无损转成结果事实时停止，等待审计迁移；不得补造 Actor/结果。
- downgrade `0210 → 0200` 仅在没有 `WITHDRAWN` 结果记录时允许；有记录时失败关闭。
- Win11 / 隔离 PostgreSQL 18 验证空库完整迁移/drift、Draft历史升降级、真实统一 Review Round START→WITHDRAWN 与 PlanVersion RETURNED 原子闭环、错Actor/错误Round/无结果/伪造RETURNED负例、Audit/结果写故障回滚及降级历史保护。
- P06-P02 继续只做内部 Plan Review Subject Owner，不挂载 HTTP、Registry 或 Windows 用户入口；真实 Source/Session/License/授权组合使用何种测试替身须在结果中逐项注明。不得将合成撤回称为客户确认。

## 风险、兼容、迁移与回滚

- 事件表为追加事实，向前升级不回填/删除旧事实；探测到现有撤回但缺Plan结果时停止升级，人工审计后另行处理。
- PlanVersion 已有对外状态 `RETURNED` 足以表达可重新修订的终态；独立 `WITHDRAWN` 事件保留“由撤回导致”的审计语义，不把Review撤回误认为客户的退回决定。
- 不变更 `/api/v1`、Review DTO/状态机、权限、License、数据外发、依赖或产品Scope。原0190、0200及Gate 2冻结内容保持不变。
- 用户2026-09-24持续自主执行授权覆盖本CR的实施；本记录不代表业务验收或Gate通过。
