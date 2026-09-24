# PRJ-03-A04：Department 停用命令

- 日期：2026-09-25；结果：PASS（内部命令，非公开 API）。
- 当前 Phase：Phase 2 Platform Core；WBS：PRJ-03-A04。
- 输入基线：Gate 2 冻结 DM-02“停用前没有 ACTIVE/SUSPENDED 成员引用”、API-01 强 ETag、API-02 `PROJECT_DEPARTMENT_DEACTIVATE` 与 `PROJECT_DEPARTMENT_IN_USE`；前置 PRJ-03-A01～A03、PRJ-02-A01～A04 PASS。
- 涉及模块：Project Application/Infrastructure，复用 Auth-owned 当前 Session/CSRF Port 与 AuditService；涉及实体：Department、ProjectMember；API：仅内部状态命令，无公开路由。
- 涉及权限：当前 ProjectManager、Session/CSRF、License、目标 Project ACTIVE、目标 Department 归属；其他角色、跨项目与归档写入拒绝。
- 验收标准：单向 ACTIVE→INACTIVE、强 expected_version、ACTIVE/SUSPENDED 成员引用拒绝、仅 REMOVED 历史可停用、与成员新建并发无矛盾状态、同事务 Audit/回滚、Windows 11/PostgreSQL 与 wheel 验证。
- 风险：项目行锁串行化当前受权 Application 写命令；直接数据库写入或未来未遵守该锁的其他命令仍需部署权限/集成测试约束。公开 POST 幂等、生产 License 和安全运行配置未接线。

Changed：新增内部 Department 停用 Service/Repository；锁定受权项目与部门并复核版本/状态，查询目标部门是否仍有 ACTIVE/SUSPENDED ProjectMember。有则返回 `PROJECT_DEPARTMENT_IN_USE`；没有则版本+1、状态 INACTIVE，并同事务写入前后状态 AuditEvent。INACTIVE 不可重复停用、不可经本命令恢复；REMOVED 成员历史和部门行均不删除。

Files：Project Department 停用 Service/Repository、单元测试、一次性 PostgreSQL 验证脚本、决策/进度/版本记录。Migration：无；升级无需数据操作。API：无新公开路由或 Breaking Change。

Tests：Windows 11/Python 3.13 后端 304/304 PASS；停用服务覆盖率 96%；PostgreSQL 18.6 临时库 ACTIVE/SUSPENDED 引用拒绝、REMOVED 历史允许、版本/状态/权限/合成 License、Audit 回滚、成员新增与停用并发仅产生一致状态、归档拒绝 PASS；wheel 构建 PASS。Windows Server 2025、Debian 13 本项未验证。

Known Issues：生产 License Guard、公开 POST Idempotency-Key/If-Match、安全运行数据库/可信 Origin 与 Key Provider 仍未接线，默认应用不能使用这些内部命令；三平台正式发行未验证。

Next：复核 `AUT-03-A07` 与 `PLT-02-A07` 的剩余生产安全装配前置，优先完成独立可实施的安全配置/协议基础，之后恢复公开路由；不得把本项内部 PASS 当成 Gate 3 通过。
