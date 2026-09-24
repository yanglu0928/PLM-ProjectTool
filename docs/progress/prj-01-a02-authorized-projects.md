# PRJ-01-A02：项目成员授权摘要读取

- 日期：2026-09-25；结果：PASS（只读摘要；非完整逐操作授权服务）；依据：冻结 DM-02 ProjectMember 状态与单项目规则、PRJ-01-A01、DEC-20260925-014。
- Changed：Project 模块公开 `ProjectAccessSummary`，在调用方事务中读取当前 User 的 ACTIVE 且已生效成员；只返回 ACTIVE Project/Department 的项目 ID、名称、角色。SUSPENDED、REMOVED、未生效成员、ARCHIVED Project、INACTIVE Department 全部不返回；不为 DeploymentAdmin 推定项目身份，也不缓存权限。Auth SessionView 经 Project 公共 DTO 与显式读 Port 取得真实摘要。
- Files：Project 公共 DTO、SQL 只读适配器、Auth DTO 映射、单元测试、临时 PostgreSQL 验证脚本、追溯文档。Migration：无。API：无新公开端点。Permission：调用者仍须验证 User/Session；本读层不代替按资源归属与动作判定的 ProjectAuthorizationService。
- Tests：Windows 11/Python 3.13 后端 237/237 PASS；读层合并覆盖率 100%；PostgreSQL 18.6 多用户隔离、空成员、有效成员、暂停/未来生效/停用部门/归档项目/移除后重分配、停用 User 的 Auth SessionView 拒绝 PASS；wheel 构建 PASS。Windows Server 2025、Debian 13 本项未运行。
- Known Issues：业务命令和正式逐操作 ProjectAuthorizationService 未实现；生产登录仍缺安全运行数据库凭据与 Origin 配置，默认 404。摘要不授予业务操作权限，每次受保护 PROJECT 操作需重新验证成员状态和资源归属。
- Next：`PRJ-01-A03 ProjectAuthorizationService 逐操作授权`；并行保留 AUT-03-A07 安全运行配置前置，不能把摘要读层当作完整登录装配验收。
