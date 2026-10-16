# EVD-01-A04-P03-A01：资格裁定当前身份与角色边界

日期：2026-10-01；Phase 2 Platform Core；结论：`INTERNAL_ACCESS_PASS / COMMAND_OPEN`。

输入：冻结 `EVIDENCE_SET_ELIGIBILITY` 的项目 PM/受权 CustomerManager 与 GLOBAL DeploymentAdmin 角色要求、S/L/C/I/M/A 安全约束。前置：现有 Session/CSRF 与 ProjectActorFacts Port；只新增 Evidence 内部资格访问层，不挂路由或写库。

在调用方事务内用当前 Session+CSRF 重新确认 actor，项目角色限 PM/CustomerManager 且项目必须 ACTIVE，项目事实加锁；GLOBAL 只允许 DeploymentAdmin。身份不符、撤权、归属异常失败关闭。License、来源版本、Evidence 行锁、If-Match、幂等和 Audit 由后续命令承担；本项不声称完成全部安全链。

定向3项单元测试通过，后端全量1785项通过/3跳过；覆盖允许角色、其他成员/移除/归档拒绝、身份和 GLOBAL 管理边界。真实 PostgreSQL/HTTP 尚未验证。回滚为撤未挂载的内部访问类，正式记录不变。
