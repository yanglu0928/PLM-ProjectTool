# PRJ-04-A13-P02：Department 列表可选 HTTP

- Phase/WBS：Phase 2 Platform Core / PRJ-04-A13-P02。来源：冻结 API-01/02、PRJ-03-A01、PRJ-04-A13-P01；决策 DEC-20260925-076。
- Changed：新增仅显式注入时挂载的 `GET /api/v1/projects/{project_id}/departments`，可信 Host、当前 Session、严格 page size/游标、项目成员授权和 License 复核。返回安全 Department page；修正内部正式 License 拒绝的错误映射。
- Compatibility/Upgrade：默认及当前 Windows 平台组合仍 404；无新 Migration/依赖或 Breaking API，升级无需数据操作。
- Tests：Windows 11/Python 3.13 后端 427/427 PASS；PostgreSQL 18 临时库双页游标、四角色读取、跨项目/暂停会话拒绝、License 403 及归档只读 PASS；开发 wheel PASS。临时库已删除，测试服务已停止。
- Result：可选 HTTP PASS；Windows 独立游标密钥来源与平台组合、正式发行信任源、Gate 3 和可用程序包未完成。
- Known Issues：Windows Server 2025/HTTPS 与 Debian 13 本项未验证；本轮 Session HTTP 预检用合成适配，内部服务对数据库当前 Session 做实际复核。
- Next：PRJ-04-A13-P03 Windows 独立 Department cursor 密钥来源与备份恢复验证。
