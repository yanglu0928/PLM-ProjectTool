# PRJ-02-A02：ProjectMember 创建命令

- 日期：2026-09-25；结果：PASS（内部命令，非公开 API）；依据：冻结 API-02 `PROJECT_MEMBER_CREATE`/`PROJECT_USER_ALREADY_ASSIGNED`、DM-02 单项目成员与部门归属、DEC-20260925-020。
- Changed：当前 ProjectManager 在 License Guard、Session/CSRF 与同事务 Project 授权后创建成员；Auth-owned Port 锁定 ENABLED 目标 User，Project-owned Repository 锁定同项目 ACTIVE Department，检查未有非 REMOVED membership，插入单一角色/部门并同事务 Audit。可选未来 effective_at；目标 User 已分配时只返回固定冲突码，不泄露另一项目。数据库 partial unique 与复合 FK 继续兜底。
- Files：Auth-owned 目标资格适配器、Project 创建成员 Service/Repository、单元测试、一次性 PostgreSQL 验证脚本、决策/进度/版本记录。Migration：无。API：无新公开路由；公开 POST 仍需 API-01 幂等键、Envelope/trace/error 映射。
- Tests：Windows 11/Python 3.13 后端 271/271 PASS；创建服务覆盖率 95%；PostgreSQL 18.6 临时库角色/CSRF/合成 License、跨项目部门拒绝、停用 User、已分配用户、两项目并发争用仅一成功、Audit 回滚、归档拒绝 PASS；wheel 构建 PASS。Windows Server 2025、Debian 13 本项未运行。
- Known Issues：生产 License/安全运行配置和公开 API 未完成；合成 Guard 不代表生产许可可用。成员角色/部门修改、暂停/恢复/移除与公开幂等仍待后续任务。
- Next：`PRJ-02-A03 ProjectMember 角色/部门修改命令`；随后状态变更命令与部门管理。
