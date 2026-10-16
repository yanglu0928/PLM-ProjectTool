# TRC-01-A05-P02：内部 TraceLink 创建

- Changed：新增 PROJECT 用户路径的内部 Trace 创建命令。真实 Session/CSRF、冻结 ProjectManager/ImplementationMember 授权、两端固定版本 Owner 证明、受控关系无环 Guard、持久幂等收据、活动边去重与 Audit 在调用方同一事务内完成；相同活动边无第二条审计。只支持已显式注册并可证明的 Owner，目前仅 `document/DOC-02`。
- Files：Trace 应用创建服务与基础设施 Repository、Project 操作授权项、单元测试、隔离 PostgreSQL 验证脚本、决策日志、状态与版本说明。Migration/公开 API/新依赖：无；版本 `0.1.0.dev0`。
- Tests：Windows 11/Python 3.13 后端 600 项无失败（2 项既有符号链接环境跳过）；隔离 PostgreSQL 18.6 真实 Session/CSRF、项目角色、同 Key 与不同 Key 同边重放、双用户并发去重、跨项目/受限文件/许可拒绝、归档写拒绝、受控关系环和 Audit 失败全回滚 PASS；开发 wheel PASS，SHA-256 `78c5313c21f87d0274369981d1fa956cd9681f4b5d4dd3db8017042d88c17a4c`。
- Result：仅内部创建路径 PASS；默认/Windows 平台均未挂载 Trace HTTP。GLOBAL/Owner Service 写路径、其他业务 Owner、正式目标环境信任源与图读取仍待。Gate 3、可用程序包、Server 2025 不标 PASS，Debian 13 按用户指令暂不验证。
- Next：TRC-01-A05-P03 可选 HTTP 契约与显式 Owner 装配前置核查。
