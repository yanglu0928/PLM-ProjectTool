# PRT-01-A05-A02：PrototypeVersion Schema0130

日期：2026-10-08。结论：`PRT_01_A05_A02_VERSION_SCHEMA_PASS`。下一项：
`PRT-01-A06-A01` Create/Read/Validate Owner 前置核查。

## 实施结果

- Migration `20261008_0130` 和 ORM 新增 `prt_prototype_versions`、
  `prt_version_artifact_refs`、`prt_version_requirement_refs`、`prt_interaction_specs`。
- Version 以 `(prototype_version_id, prototype_id, project_id)` 为复合身份；Root 的
  `current_approved_version_ref` 通过延迟复合 FK 只能指向同 Prototype、同 Project 的 Version。
- 固定同 Template 的 `template_ref + template_version_ref`，Version 链只能在同 Prototype/Project 内
  supersede；Review/ReviewRound 必须成对为空或非空。
- Artifact、Requirement 使用有序且不重复的固定引用；Requirement 复合 FK 固定同项目 RequirementVersion。
  InteractionSpec 每 Version 最多一条，保存 schema v1 JSON 对象和 32 字节内容指纹。
- Schema 固定声明范围：1～100 Artifact、1～200 Requirement、恰一条 Interaction。A06 Owner 开放前四表
  全部拒绝行级写入及 TRUNCATE，避免形成无 Audit/receipt/完整集合闭包的半成品历史。
- DRAFT Schema 不推进正式指针；APPROVED 状态和指针推进仍由 A07 Review/Formalize 窄门负责。

## 验证证据

- Windows 11/PostgreSQL 18.6：已有数据从 0129 升级，空历史降级/重升、Alembic drift、Owner 关闭、
  Root/Template/Requirement 复合 FK、计数/JSON/顺序约束、TRUNCATE 拒绝及有历史拒绝降级全部通过。
  合成验证数据及隔离数据库已销毁。
- 定向测试：20 项、21 个 subtest 通过。
- 全量后端：3123 项通过、3 项条件跳过、4666 个 subtest 通过；仅保留既有 TestClient/anyio 弃用告警。
- `compileall` 通过。开发 wheel 共 1196 项并包含 Migration0130 与 ORM，SHA-256：
  `f7ec21d7fdb3e07f6b63f26f50733521f5faccf51363758f6518304a4925b656`。

## 偏差与处理

- 首次 PostgreSQL 验证夹具在存在 deferred FK pending event 时尝试重新启用触发器，PostgreSQL 正确拒绝；
  这是合成夹具时序问题，不是产品 Migration 缺陷。夹具改为事务局部 `session_replication_role` 后完整重跑通过，
  该绕过只用于准备一致的既有基线数据，所有待验约束均在正常角色下执行。
- 首次全量回归发现 ORM 历史清单未登记四张新增表；补齐精确物理表名后定向和全量回归均通过。没有放宽
  Schema 约束或删除既有断言。

## 兼容、升级与回滚

0130 是前向加表和 Root FK 的兼容迁移，既有 Root 指针均为空，不改变冻结 `/api/v1`、依赖、AI 外发、
License 或目标环境。四表为空时可降回 0129；任何 PrototypeVersion 历史存在时拒绝破坏性降级。应用可停止
后续 Owner 装配，但不得删除版本、引用、交互、Review 或 Audit 历史。

Windows Server 2025 本项未实机运行，不能由 Windows 11 结果外推；Debian 13 按用户指令跳过。A06 Owner、
A07 Review/Formalize、HTTP、前端、Gate 3、UAT 和可使用程序包仍待客观关闭，Gate 3 保持 BLOCKED。
