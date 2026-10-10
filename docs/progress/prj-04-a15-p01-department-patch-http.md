# PRJ-04-A15-P01：Department 修改可选 HTTP

- Phase/WBS：Phase 2 Platform Core / PRJ-04-A15-P01。来源：冻结 API-01/02、PRJ-03-A03；决策 DEC-20260925-082。
- Changed：显式注入时提供 `PATCH /api/v1/projects/{project_id}/departments/{department_id}`；可信 Origin、当前 Session/CSRF、强 If-Match、严格 JSON；复用内部 License/ProjectManager/并发/审计服务。200 返回安全 DepartmentView/ETag；默认应用 404。
- Compatibility/Upgrade：冻结 `/api/v1` 不变，无 Migration/依赖；目标库需已升级至 `20260925_0018`。
- Tests：Windows 11/Python 3.13 后端 437/437 PASS；PostgreSQL 18 临时库真实 HTTP 修改、版本冲突、非负责人/跨项目拒绝、License 拒绝、无变化不新增 Audit、并发与回滚及开发 wheel PASS。临时库已删除，测试服务已停止。
- Result：可选 HTTP PASS；Windows 平台组合、正式信任源、Gate 3 与最终程序包未完成。
- Known Issues：Server 2025/HTTPS 与 Debian 13 本项未验证；合成 License 不代表正式发行验收。
- Next：PRJ-04-A15-P02 在 Windows 显式平台组合接入部门 PATCH。
