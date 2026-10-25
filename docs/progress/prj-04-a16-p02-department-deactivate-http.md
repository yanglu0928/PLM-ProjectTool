# PRJ-04-A16-P02：Department 停用可选 HTTP

- Phase/WBS：Phase 2 Platform Core / PRJ-04-A16-P02。来源：冻结 API-01/02、PRJ-03-A04、CR-PRJ-005、PRJ-04-A16-P01；决策 DEC-20260925-085。
- Changed：显式注入时提供 `POST /api/v1/projects/{project_id}/departments/{department_id}:deactivate`；可信 Origin、Session/CSRF、强 If-Match、Idempotency-Key、空请求体；复用内部持久幂等服务，200 返回安全 DepartmentView/ETag。默认应用 404。
- Compatibility/Upgrade：冻结 `/api/v1` 不变，无新 Migration/依赖；目标库须升级至 `20260925_0019`。
- Tests：Windows 11/Python 3.13 后端 441/441 PASS；PostgreSQL 18 临时库真实 HTTP 首次/同 Key 重放 200 仅一次停用/Audit/快照、版本冲突、非负责人、成员在用 409、合成 License 403 与开发 wheel PASS。临时库已删除，测试服务已停止。
- Result：可选 HTTP PASS；Windows 平台组合、正式信任源、Gate 3 和可用程序包未完成。
- Known Issues：Server 2025/HTTPS 与 Debian 13 本项未验证；合成许可不代表正式发行验收。
- Next：PRJ-04-A16-P03 在 Windows 显式平台组合接入部门停用。
