# PRJ-04-A06：Project 元数据 PATCH HTTP

- Phase/WBS：Phase 2 Platform Core / PRJ-04-A06。输入：冻结 Project PATCH/ETag 合同、PRJ-01-A06 内部写服务与 `DEC-20260925-058`。
- Changed：新增可选 `PATCH /api/v1/projects/{project_id}`，只接纳 `name`；可信来源、Session、CSRF、强 `If-Match`、当前 ProjectManager、License 与同事务 Audit 由既有组件保护。修复通用解析器接受规范初始 ETag `"v0"`，拒绝非规范形式。
- Files：Project PATCH 路由、应用可选装配、If-Match/错误映射、HTTP 契约及临时库验证、决策/状态/版本记录。
- Migration：无。API：符合冻结 `/api/v1` 合同，无 Breaking Change；默认及当前 Windows 平台组合暂不挂载，需下一 WBS 装配。
- Tests：Windows 11/Python 3.13 后端 393/393 PASS；PostgreSQL 18 临时库 HTTP 首次 v0→v1、陈旧版本 409、跨项目 404、缺 If-Match 428、Audit 一次、内部 License/审计回滚/归档保护 PASS；开发 wheel 构建 PASS。临时库已删除，数据库服务已停止。
- Result：可选 HTTP 接口及隔离合成端到端 PASS；PRJ-04 整体、Gate 3 与可用程序包未完成。
- Known Issues：Windows 显式平台装配、正式发行信任源、Server 2025/HTTPS 和 Debian 13 尚未验证。
- Next：PRJ-04-A07 将该 PATCH 路由接入 Windows 显式平台组合并实测真实 Session/数据库与合成 License。
