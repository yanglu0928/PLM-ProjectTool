# PRJ-04-A10-P02：成员创建可选 HTTP

- Phase/WBS：Phase 2 Platform Core / PRJ-04-A10-P02。输入：冻结 API-01/02、PRJ-04-A10-P01 内部幂等及当前 Session/CSRF/License 安全边界；决策 DEC-20260925-068。
- Changed：新增仅显式注入的 `POST /api/v1/projects/{project_id}/members`。严格可信 Origin、唯一 Cookie/CSRF/Idempotency-Key、现行 Session、8 KiB UTF-8 JSON 与 canonical UUID；ProjectId 仅来自路径。201 复用安全 MemberView 投影及强 ETag/Location，不回显内部快照或收据。默认与当前生产组合不挂载，仍 404。
- Files：Project 成员创建 Router、应用工厂可选注入点、HTTP 契约与临时 PostgreSQL 验证、决策/状态/版本说明。
- Migration：无新增；目标库须已有 `20260925_0016`。API：冻结路径的可选实现，无 Breaking Change。
- Tests：Windows 11/Python 3.13 后端 413/413 PASS；PostgreSQL 18 临时库真实 Session 同 Key 两次 201 仅一成员/Audit、异载荷 409、非负责人和跨项目 404、合成 License 拒绝 403 PASS；开发 wheel PASS。临时库已删除，服务停止。
- Result：可选 HTTP 与隔离合成端到端 PASS；Windows 显式平台组合、正式信任源、PRJ-04 整体、Gate 3 和可用程序包未完成。
- Known Issues：Windows Server 2025/HTTPS 与 Debian 13 本项未验证；正式目标账户材料和生产 License 尚待供给。
- Next：PRJ-04-A10-P03 将成员创建挂入 Windows 显式平台组合并复验门禁及真实会话。
