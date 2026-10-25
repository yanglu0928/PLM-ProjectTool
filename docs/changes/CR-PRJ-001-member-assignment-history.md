# CR-PRJ-001：ProjectMember 角色与部门变更历史持久化

日期：2026-09-25；状态：依据 CR-EXEC-001 的持续授权批准执行；范围：PRJ-02-A03。

## 差异与证据

Gate 2 冻结的 DM-02 要求 `RoleAssignment` 属于 ProjectMember 的当前角色及变更历史。冻结 SC-01 将 ProjectMember 映射到 `prj_project_members`，无强制子表；实际 Migration `20260925_0013` 只保存当前 `project_role`、`department_id` 和版本。通用 AuditEvent 只记录动作、对象和状态，不包含旧/新角色与部门。因此直接 PATCH 会覆盖原值，无法反查变更历史。

## 选择与范围

比较：仅覆盖当前字段并依赖通用 AuditEvent 无法还原旧/新角色与部门，拒绝；将旧/新值塞入 AuditEvent 的状态码字段不能完整保存部门 UUID，也会污染通用审计语义，拒绝；新增 Project-owned 历史表能够保持变更前后值和版本，同时维持跨模块边界，选择此方案。

新增 Project-owned、仅追加的 `prj_member_assignment_history`，在同一事务记录成员 ID、项目 ID、变更前/后的角色和部门、执行者、TraceId、前后版本及时间。当前值仍只保存在 `prj_project_members`，授权实时读取当前值；历史表不单独成为聚合或对外可写资源。保持现有 `/api/v1` 路径、角色枚举与安全边界不变。创建成员的初值由成员表和既有创建 AuditEvent 表示；本表记录 PATCH 变更，不伪造历史迁移前事件。

## 影响、验证和回退

DB Schema V1 需增加一个实现性子表、ORM 和 Alembic Migration；这是冻结后的增量变更，原冻结提交不改。空库与已有数据升级均只建表，不改原成员数据。PATCH 必须检查当前 ProjectManager、Session/CSRF、License、归属、活动部门、强 ETag，并同事务写当前值、历史与 AuditEvent；错误/审计失败整体回滚。迁移降级仅在历史表为空时允许，避免丢失追溯证据。发布升级前应备份数据库并执行 `upgrade head`。公开 HTTP 接线、真实生产 License/Secret 和 Server 2025/Debian 13 本项验证不由此 CR 宣称完成。
