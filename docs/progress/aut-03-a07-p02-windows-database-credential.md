# AUT-03-A07-P02：Windows 数据库凭据来源

- 日期：2026-09-25；结果：PASS（Windows 11 组件验证；AUT-03-A07 生产登录仍未通过）。
- 当前Phase：Phase 2 Platform Core；当前WBS：AUT-03-A07-P02。
- 输入基线：Gate 2 安全边界、CR-AUT-002、CR-AUT-003。
- 前置任务：数据库运行层、AUT-03-A07-P01 PASS。
- 涉及模块：Platform Infrastructure 与本机部署入口；涉及实体：无；涉及API：无公开 API；涉及权限：Windows Credential Manager 当前运行账户范围，不授予应用业务权限。
- 验收标准：固定默认 Target、无回显交互写入/轮换、同一账户读取、错误不泄露 Secret、非法 URL/Target 和不支持平台失败关闭、合成凭据 Windows 11 往返、回归与 wheel 构建通过。
- 风险：运行账户必须与录入账户相同；账户/机器恢复须由管理员从独立保管的数据库凭据重录；Python/SQLAlchemy 运行期内存不能保证绝对清零。

Changed：新增 Windows Credential Manager Generic Credential 读取/写入适配和无参数、无回显本机录入入口；默认 Target 为 `PLMProjectTool/Database`。CLI 不接受 URL 命令行参数，仓库和普通 Bootstrap 配置不保存密码。测试仅创建唯一 UUID 的合成 Target，测试完成即删除该测试条目；生产默认 Target 未触碰。

Files：`windows_database_credential.py`、`provision_database_credential.py`、组件测试、CR/决策/进度/状态/版本说明。Migration：无，升级无需数据操作。API：无新公开路由或 Breaking Change。

Tests：Windows 11/Python 3.13 后端 309/309 PASS；Windows Credential Manager 合成 URL 写入、读取、轮换、缺失/非法值拒绝 PASS；wheel 构建 PASS。Windows Server 2025 实际运行账户/服务验证未做，Debian 13 凭据来源仍待实现且按用户指令暂不验证。

Known Issues：本组件不自动装配数据库/登录；生产部署需由目标运行账户现场录入真实 URL，仍需可信 Origin 最终语义校验、Project 真实摘要及端到端登录验证。默认登录路由保持 404，Gate 3/UAT 未通过。

Next：恢复 AUT-03-A07 生产组合根，以安全读取的 URL、可信 Origin 策略及真实 Project 授权摘要完成 PostgreSQL 端到端登录；继续规划 Debian 安全来源和 Windows Server 2025 验证。
