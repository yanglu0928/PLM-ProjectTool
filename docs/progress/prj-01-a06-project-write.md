# PRJ-01-A06：Project 元数据修改与归档内部命令

- 日期：2026-09-25；结果：PASS（内部命令，非公开 API）；依据：冻结 API-01 强 ETag/If-Match、API-02 `PROJECT_PATCH`/`PROJECT_ARCHIVE`、DM-02 项目状态与编码不可静默复用、DEC-20260925-018。
- Changed：ProjectManager 通过当前 Session/CSRF 与 License Guard 后，在同一写事务锁定 Project/Member/Department 权限事实；按 expected lock_version 修改显示名称或单向归档，递增版本并同事务写 Audit。无成员、跨项目及非管理角色隐藏；已归档项目拒绝新写，旧版本返回 `CONFLICT_VERSION`。通用 PATCH 不更改 ProjectCode，旧码保留问题留待正式受控变更。
- Files：Auth-owned Project 写入身份适配器、Project 写服务/SQL Repository、授权服务同事务锁定入口、单元测试、一次性 PostgreSQL 验证脚本、决策/进度/版本记录。Migration：无。API：无新公开路由，后续 HTTP 层仍需 If-Match/Idempotency/Envelope/trace/error 映射。
- Tests：Windows 11/Python 3.13 后端 259/259 PASS；Project 写服务覆盖率 96%；PostgreSQL 18.6 临时库真实 Session/CSRF、权限即时变化、合成 License 拒绝、Audit 失败回滚、强 ETag 冲突与单向归档 PASS；wheel 构建 PASS。Windows Server 2025、Debian 13 本项未运行。
- Known Issues：生产 License/安全运行配置与公开路由未完成；不能对外宣称项目管理可用。归档后其他模块的新写和 Job 拒绝仍须各 Owner 后续接线验证。若确需改项目编码，应先设计旧码永久保留与升级，不得通过名称 PATCH 绕过。
- Next：`PRJ-02-A01 ProjectMember 授权列表读取`；随后成员创建/角色变更/暂停/恢复/移除和部门管理。
