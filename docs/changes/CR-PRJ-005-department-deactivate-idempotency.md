# CR-PRJ-005：Department 停用持久幂等与错误码

日期：2026-09-25；状态：依据 CR-EXEC-001 持续授权批准实施；范围：PRJ-04-A16 部门停用公开 API 前置。

## 冲突与证据

冻结 API-01 要求可重试状态 POST 携带 Idempotency-Key，并在同 Key/同请求时重放首次语义响应；冻结 API-02 将部门停用列为 `S,L,C,I,M,A`，要求部门仍有 ACTIVE/SUSPENDED 成员时返回 `PROJECT_DEPARTMENT_IN_USE`。现有 `ProjectDepartmentDeactivateService.deactivate` 是非幂等内部命令：成功后重复调用会因版本/状态返回 409；`COMMON_ERRORS` 尚未登记该业务错误码。当前不可直接挂载公开路由。

## 方案比较与选择

- 不选将重复停用视为普通成功：不能复原首次 DepartmentView/ETag，亦无法区分异载荷重放。
- 不选读取当前部门行重建首次结果：后续变化会导致历史响应漂移。
- 选择复用通用持久收据，新增 Project-owned、仅追加的 Department 停用首次结果快照；同事务写入状态、审计、快照及收据。同 Key 同规范请求在复核 Session/CSRF、License、当前 ProjectManager 身份后重放原结果；异载荷冲突。公开 HTTP 另立 WBS 接线。按冻结业务语义登记 `PROJECT_DEPARTMENT_IN_USE` 为 409 安全错误。

## 差异、风险、迁移与回滚

这是 Gate 2 冻结 DB Schema 后的可追溯增量，不回写原冻结版本。新增 ORM/Alembic Migration，保留旧内部命令；无新增外部依赖或 `/api/v1` Breaking Change。目标库升级前备份，空表允许 down；有停用快照时拒绝普通降级以保护幂等证据。风险包括同 Key 并发竞态、成员引用检查与收据写入不原子、重放绕过身份/许可、归档后历史重放语义，以及快照被修改。

## 验证计划与边界

验证 ORM/Migration 差异、空库 up/down、有数据升级、同 Key 顺序及并发重放、异载荷冲突、停用后原 ETag/视图快照、成员在用拒绝、审计失败回滚、快照不可变、非空降级拒绝；随后独立验证可选 HTTP、两种 Windows 平台组合与缺信任源关闭。仅 Windows 11/Python 3.13、PostgreSQL 18 临时库可作为当前证据；正式目标账户信任材料、Server 2025/HTTPS 与 Debian 13 不据此宣称通过。
