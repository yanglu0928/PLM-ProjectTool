# PRJ-04-A09-P02：Project Member 列表可选 HTTP

- Phase/WBS：Phase 2 Platform Core / PRJ-04-A09-P02。输入：冻结 `PROJECT_MEMBER_LIST`、PRJ-02-A01 内部授权分页、P01 HMAC cursor；决策 `DEC-20260925-064`。
- Changed：新增可选 `GET /api/v1/projects/{project_id}/members`，当前 Host/Session 与 ProjectManager/CustomerManager 授权，唯一 page_size/cursor 白名单、安全 MemberView Page。修正内部已知 License 拒绝的错误映射为 403。默认及当前平台组合仍 404。
- Files：Project Member 读服务/HTTP Router、应用可选装配、单元/契约/临时库验证、决策/状态/版本记录。
- Migration：无。API：符合冻结 `/api/v1`，无 Breaking Change。
- Tests：Windows 11/Python 3.13 后端 405/405 PASS；PostgreSQL 18 临时库真实成员历史两页、负责人/客户负责人、跨项目/其他角色隐藏、跨会话 cursor 400、License 403 PASS；开发 wheel 构建 PASS。临时库已删除，数据库服务停止。
- Result：可选 HTTP 和隔离合成端到端 PASS；Windows 显式平台密钥供给/组合、PRJ-04 整体、Gate 3 和可用程序包未完成。
- Known Issues：正式账户独立 cursor 密钥、发行信任源、Server 2025/HTTPS、Debian 13 未验证。
- Next：PRJ-04-A09-P03 Windows 独立成员 cursor 密钥安全来源及恢复验证；之后显式平台组合。
