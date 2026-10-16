# REQ-01-A02：Package / Requirement 身份与成员关系 Schema

日期：2026-10-07。结论：`REQ_01_A02_IDENTITY_SCHEMA_PASS`。下一项：`REQ-01-A03`
Package / Requirement identity 内部 Owner、状态、持久幂等与 Audit。

## 实现

- 新增 Requirement bounded context ORM，物理化 `req_packages`、`req_requirements` 和
  `req_package_memberships`，并在 Alembic metadata 注册。
- Package、Requirement 均以组合唯一键固定 Project 归属；membership 同时引用
  `(requirement_package_id, project_id)` 与 `(requirement_id, project_id)`，从数据库层拒绝跨项目成员。
- Requirement code 以原值和 `upper(requirement_code)` 规范值保存，项目内规范值唯一；状态固定为
  `ACTIVE / DEFERRED / REJECTED / ARCHIVED`。Package 状态采用记录在 DEC-975 的
  `ACTIVE / ARCHIVED / RESTRICTED`。
- Migration0111 在 A03 Owner 前仅允许合法初态 INSERT，禁止更新、删除和截断；正式版本指针必须为
  NULL。空历史支持 0111→0110→0111，存在历史拒绝降级。

## 验证

- Windows 11 / PostgreSQL 18.6 隔离临时库：已有平台数据从 0110 升级、空历史降级/重升、
  Alembic `check`、三表 inventory、同项目 membership、跨项目/重复成员/重复规范 code/坏规范值/
  悬空正式指针/修改/删除/截断负例和历史拒降全部通过；两个临时库均强制清理。
- Schema/Migration/metadata 定向 11 项通过；后端全量 2961 项通过、3 项既有环境条件跳过、0 失败。
- Python `compileall` 通过。开发 wheel 共 1113 项并包含 Requirement ORM 与 Migration0111，SHA-256
  `d9ad6fce63e2312af68f0507170e22737fdf4e5360a7c6bc44a829312d40f8ea`；它不是正式发行包。

本项无公开 API、依赖、Secret、客户数据或外发变化。尚未实现 A03 Owner、A04 Version/正式指针外键、
HTTP/UI/Workflow，也不表示 Requirement 业务可用、Gate 3 或 UAT 通过。
