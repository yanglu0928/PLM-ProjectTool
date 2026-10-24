# PRJ-01-A03：ProjectAuthorizationService 逐操作授权

- 日期：2026-09-25；结果：PASS（Project 路径内操作授权核心；非公开 API 或完整业务命令）；依据：冻结 API-02 Project 角色矩阵、DM-02 ProjectMember、DEC-20260925-015。
- Changed：Project 模块增加默认拒绝的 13 项路径内操作策略；每次在当前事务读取成员、部门、项目状态；成员/部门目标重新查询项目归属，跨项目、无成员、无权限或目标不存在统一拒绝；有权限的归档项目只读，禁止写。Project 列表和部署级创建另行实现，不在路径内角色矩阵中。
- Files：Project application 授权服务、SQLAlchemy 事实与归属适配器、角色矩阵单元测试、一次性 PostgreSQL 验证脚本、决策和版本记录。Migration：无。API：无新公开端点。Permission：调用方仍须先完成 Auth Session/CSRF 与 License Guard；服务不代表这些前提已接线。
- Tests：Windows 11/Python 3.13 后端 241/241 PASS；授权服务单元覆盖率 98%；PostgreSQL 18.6 临时库真实角色变更、暂停/未来生效成员、停用部门、跨项目成员/部门目标、归档只读验证 PASS；wheel 构建 PASS。Windows Server 2025、Debian 13 本项未运行。
- Known Issues：业务命令和生产 Auth/License 安全装配尚未完成，默认无公开 Project 路由；目标成员自身的业务状态迁移合法性由后续命令服务验证，授权服务只判断操作者权限与目标归属。
- Next：`PRJ-01-A04 Project 创建命令`，然后按冻结契约逐项实现成员/部门命令；AUT-03-A07 安全运行配置前置和 PLT-02-A07 仍独立保留。
