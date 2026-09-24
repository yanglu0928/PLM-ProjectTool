# PRJ-02-A04：ProjectMember 暂停/恢复/移除命令

- 日期：2026-09-25；结果：PASS（内部命令，非公开 API）。
- 当前 Phase：Phase 2 Platform Core；WBS：PRJ-02-A04。
- 输入基线：Gate 2 冻结 DM-02 的 `ACTIVE ↔ SUSPENDED`、`ACTIVE/SUSPENDED → REMOVED` 与 API-01/02 的强 ETag、逐操作权限和强制 Audit。
- 前置任务：PRJ-01-A01～A06、PRJ-02-A01～A03 PASS；Auth Session/CSRF、License Guard Port、AuditService 与成员读投影已存在。
- 涉及模块：Project Application/Infrastructure，复用 Auth-owned 最小用户显示名适配器及 Audit 公共 Port。
- 涉及实体：ProjectMember、Department；API：仅内部 `PROJECT_MEMBER_SUSPEND/RESUME/REMOVE`，无公开路由。
- 涉及权限：当前 ProjectManager、Session/CSRF、License、Project 状态与目标成员归属，拒绝跨项目；最后一位有效 ProjectManager 不可被暂停或移除。
- 验收标准：合法状态转换、预期版本、恢复前活动部门、移除时间约束、同事务 Audit/回滚、测试及 wheel 构建。
- 风险：公开 POST 幂等、If-Match、安全运行 License 接线和跨平台发行仍待后续；不能把内部 PASS 当成正式可用 API。

Changed：新增 ProjectMember 状态 Service/Repository；暂停和恢复保留成员历史身份，移除只标记 REMOVED、不物理删除，版本逐次增加。恢复时检查部门仍 ACTIVE。未来生效成员若被提前移除，`ended_at` 取 `effective_at` 与当前数据库时间较晚者，使 DB 时间不变量保持成立；状态立即 REMOVED。对最后一个当前有效负责人暂停/移除返回 `PROJECT_ROLE_INVALID`，防止管理权被清空。每次成功转换同事务写入带前后状态的 AuditEvent；审计失败整体回滚。

Files：Project 状态 Service/Repository、单元测试、临时 PostgreSQL 验证脚本、进度/决策/版本记录。Migration：无；升级无需数据步骤。API：无公开路由或 Breaking Change。

Tests：Windows 11/Python 3.13 后端 284/284 PASS；状态 Service 覆盖率 95%；PostgreSQL 18.6 临时库状态转换、版本/CSRF/合成 License、跨项目隐藏、活动部门、最后负责人、未来成员移除、Audit 回滚、归档拒绝 PASS；wheel 构建 PASS。Windows Server 2025、Debian 13 本项未验证。

Known Issues：公开 POST 的 Idempotency-Key/If-Match 和生产 License 未接线；本项只验证合成 Guard。管理角色原已有成员分配问题时，内部状态命令不提供超出冻结权限策略的紧急恢复入口。

Next：`PRJ-03-A01 Department 授权列表读取`，随后部门创建/修改/停用及 AUT-03-A07、PLT-02-A07 前置收口。
