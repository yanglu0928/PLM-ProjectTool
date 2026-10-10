# PRJ-01-A01：Project/Department/ProjectMember 持久层

- 日期：2026-09-25；结果：PASS（Schema/ORM，不含业务命令或授权读服务）；依据：冻结 DM-02、SC-01～03、CR-AUT-002、DEC-20260925-013。
- Changed：新增 `plm.prj_projects`、`plm.prj_departments`、`plm.prj_project_members`。Project code 部署内唯一；同项目 ACTIVE Department code 唯一；未 REMOVED 用户只能有一条有效成员；Member 的 Department 与 Project 使用复合 FK 锁定同一项目。各表保留状态、时间和 lock_version，Project 不保存 current_stage。
- Files：Project ORM、Alembic `20260925_0013`、元数据/迁移回归测试、临时 PostgreSQL 验证脚本与追溯文档。API：无。Permission：尚未实现真实 ProjectAuthorizationService，不开放 Project 路由或登录生产装配。
- Tests：Windows 11/Python 3.13 后端 235/235 PASS；PostgreSQL 18.6 空库 up/down/re-up、已有 User 升级、ORM drift=0、跨项目 Department 绑定拒绝、code/有效成员唯一及有数据 downgrade 拒绝 PASS；wheel 构建 PASS。Windows Server 2025、Debian 13 本项未运行。
- Upgrade：先备份并执行 Alembic `upgrade head`；现有 User/Session 等表不改。Downgrade 仅三张 Project 表全空且无下游引用时允许；有项目事实不得删除以回退。
- Known Issues：Project/Department/Member 写命令、状态转换、授权查询及项目数据权限测试仍未实现；Schema 不能被视为 Project 模块可用。归档项目写入保护和停用部门迁移规则须在业务命令/约束任务验证。
- Next：`PRJ-01-A02 项目成员授权摘要读取`，使登录 SessionView 能取得真实当前成员事实；之后再恢复 AUT-03-A07 的其他装配前置。
