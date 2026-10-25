# CR-PRJ-004：部门创建幂等结果快照

日期：2026-09-25；状态：依据 CR-EXEC-001 持续授权批准执行；范围：PRJ-04-A14 幂等前置。

## 冲突与证据

冻结 API-01 要求可重试 POST 同一 Idempotency-Key 与同一请求重放首次成功的语义响应。现有 `ProjectDepartmentCreateService.create` 每次插入，第二次遇活动编码唯一约束返回冲突；通用 `plt_idempotency_receipts` 只存结果引用。Department 的 code、name、state、created_at、ETag 后续会变化，直接读取当前 `prj_departments` 无法还原首次 201 响应。

## 方案比较与选择

- 不选从当前部门行重建：后续 PATCH/停用导致响应漂移。
- 不选将完整响应放入通用收据：破坏最小化与 Project 模块数据归属。
- 选择 Project-owned、仅追加的 `prj_department_create_results`，保存首次 DepartmentView 的类型化字段和 ProjectId；通用收据只保存结果引用。首次创建、结果快照、Audit、收据在同一事务提交。重放先复核当前 Session/CSRF、License 与 ProjectManager 身份；同 Key/同规范请求返回原视图，不重复插入或审计。不同请求同 Key 返回冲突。已归档项目仅允许既有成功重放，不允许新创建。

## 差异、风险与迁移

新增 DB Schema V1 后续增量 Migration `20260925_0018`，不回写 Gate 2 原冻结提交；冻结 `/api/v1` 路径/响应不变、无新依赖。空库和有数据升级只创建快照表，不补造历史结果。升级前人工备份；空表可降级，非空时拒绝普通降级，避免丢失幂等证据。旧内部非幂等命令保留，公开 POST 下一任务单独接线。

## 验证与剩余风险

验证 ORM/Migration 一致、空库 up/down、有数据升级、同 Key 顺序/并发重放、异请求冲突、创建后名称/状态变化重放、归档后重放、审计失败原子回滚、快照不可变与非空降级拒绝。Windows 11/Python 3.13 与 PostgreSQL 18 临时库执行。正式信任源、Windows Server 2025 与 Debian 13 不由本项宣称通过。
