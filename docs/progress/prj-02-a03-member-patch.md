# PRJ-02-A03：ProjectMember 角色/部门修改命令

- 日期：2026-09-25；结果：PASS（内部命令，非公开 API）。
- 当前 Phase：Phase 2 Platform Core。当前 WBS：PRJ-02-A03。
- 输入基线：Gate 2 冻结 DM-02、SC-01/02、API-01/02；增量依据 `docs/changes/CR-PRJ-001-member-assignment-history.md`。
- 前置任务：PRJ-01-A01～A06、PRJ-02-A01～A02 PASS；Auth Session/CSRF、License Guard Port、AuditService 已存在。公开 HTTP/生产 License 装配不属本项前置。
- 涉及模块：Project Application/Infrastructure，Auth 最小用户显示名 Port，Audit 公共 Port；不修改 Auth 表或 Audit Schema。
- 涉及实体：ProjectMember、Department、ProjectMemberAssignmentHistory；API：冻结的 `PROJECT_MEMBER_PATCH` 内部命令实现，未开放 HTTP 路由。
- 涉及权限：当前 ProjectManager、Session/CSRF、License、Project 归属/活动状态；目标成员归属二次锁定，跨项目隐藏；最后一个有效 ProjectManager 不可降级。
- 验收标准：强 expected_version、同项目 ACTIVE Department、角色枚举、当前值/历史/Audit 同事务、失败回滚、空库与已有数据升级和安全降级、单元测试及 wheel 构建。
- 风险：冻结 Schema 原无角色/部门历史，已通过 CR-PRJ-001 增量实现；公开路由幂等/If-Match、安全运行接线及跨平台发行仍待后续。

Changed：新增 `prj_member_assignment_history`、Migration `20260925_0014` 和内部 PATCH Service/Repository；无变化时不增加版本/历史/审计。历史记录保留前后角色、部门、版本及 TraceId，同事务 Audit。版本不符返回 `CONFLICT_VERSION`；不存在/跨项目 `RESOURCE_NOT_FOUND`；非法部门/移除成员/唯一负责人降级返回 `PROJECT_ROLE_INVALID`。历史表已有记录时拒绝 downgrade。

Files：Project ORM、Migration、PATCH Service/Repository、Auth 显示名适配器、单元及 PostgreSQL 验证脚本、CR/决策/进度/版本记录。Migration：`20260925_0014`；升级前备份，执行 `upgrade head`。API：无新公开路由或 Breaking Change。

Tests：Windows 11/Python 3.13 后端 278/278 PASS；PATCH Service 单元覆盖率 95%；PostgreSQL 18.6 临时库空库/已有数据升级、空表降级、有记录降级拒绝、ORM drift=0、Session/CSRF/跨项目/版本、活动部门、最后负责人、Audit 回滚及归档拒绝 PASS；wheel 构建 PASS。Windows Server 2025、Debian 13 本项未验证。

Known Issues：生产 License Guard、公开 PATCH 的 HTTP If-Match/幂等和跨平台发行仍未完成；本项验证使用合成 License。数据库表由应用约定只追加，物理防篡改仍依赖部署角色权限策略，不能把本项视为生产审计保全验证。

Next：`PRJ-02-A04 ProjectMember 暂停/恢复/移除命令`。
