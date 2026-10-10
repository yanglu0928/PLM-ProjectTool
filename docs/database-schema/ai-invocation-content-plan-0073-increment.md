# AI-04 Schema0073：新 Invocation 的 Content Plan 同源守卫

日期：2026-10-03；状态：`SCHEMA_PASS`；依据 CR-AI-015/016、DEC-741/742；上游 `20261003_0072`。

本增量不新增表或列，只增加 `trg_ai_invocations__content_plan_insert`。每个新 `ai_invocations` 行必须使用 `AUTHORIZED` 快照和非空 Content Plan，并在数据库内同时满足：

- Invocation 与 Task 的 Scope、Project、输入摘要、Prompt、Schema 和 PlanRef 一致；
- Invocation 与授权快照的 Provider/Config/Model、来源摘要、批准 payload 摘要、状态和 PlanRef 一致；
- Content Plan 与 Task/Invocation 的任务类型、策略版本、参数摘要、Context、Provider/Model/revision、Prompt/Schema 与 payload 摘要一致。

既有 `content_plan_ref IS NULL` 的 Invocation 历史原样保留，但升级后不能新增 NULL 或跨 Plan Invocation。守卫只验证不可变历史快照同源；当前授权、License、Job Lease/Fencing 与内容 Owner 的活性仍由应用层在网络 I/O 前重新验证。

升级无数据回填。无非空 Invocation PlanRef 时可降回0072；一旦产生新Plan绑定Invocation，降级拒绝，须向前修复或从受控备份恢复。Windows 11/PostgreSQL 18.6 已完成空库、历史NULL库升降/重升、drift、负例与拒降验证。
