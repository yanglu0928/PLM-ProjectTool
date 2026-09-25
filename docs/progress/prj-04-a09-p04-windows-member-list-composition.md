# PRJ-04-A09-P04：Windows 显式平台成员列表组合

- Phase/WBS：Phase 2 Platform Core / PRJ-04-A09-P04。输入：P02 可选成员列表、P03 独立 Vault cursor 密钥来源、既有 Windows 显式平台组合；决策 `DEC-20260925-066`。
- Changed：`--platform`/`--platform-write` 在 Schema/License/Secret cursor 后继续检查独立成员 cursor 密钥，缺失则释放数据库并拒绝启动；复用真实 Session、Project 授权、Auth 用户摘要和成员 SQL 读层挂载列表。默认登录模式仍 404。
- Files：Windows 组合根、组合契约与 5 组临时 PostgreSQL 回归验证、决策/状态/版本记录。
- Migration：无。API：挂载冻结 `GET /api/v1/projects/{project_id}/members`，无 Breaking Change。
- Tests：Windows 11/Python 3.13 后端 408/408 PASS；临时 PostgreSQL 18 成员列表真实 Session 双页/跨会话 cursor/角色隔离/合成 License 拒绝，以及 Project 创建/读取/修改归档和 Secret 写组合回归均 PASS；开发 wheel 构建 PASS。临时库已删除，数据库服务停止。
- Result：Windows 显式组合和隔离合成端到端 PASS；正式成员 cursor 密钥、发行信任源、PRJ-04 整体、Gate 3 和可用程序包未完成。
- Known Issues：Windows Server 2025/HTTPS、Debian 13 未验证；正式目标账户须独立供给/离线备份密钥。
- Next：PRJ-04-A10 Project Member 创建 HTTP 前置核查，重点冻结幂等要求。
