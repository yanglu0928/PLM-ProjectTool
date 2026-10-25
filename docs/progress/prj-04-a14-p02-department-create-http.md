# PRJ-04-A14-P02：Department 创建可选 HTTP

- Phase/WBS：Phase 2 Platform Core / PRJ-04-A14-P02。来源：冻结 API-01/02、PRJ-03-A02、PRJ-04-A14-P01；决策 DEC-20260925-080。
- Changed：新增仅显式注入时挂载的 `POST /api/v1/projects/{project_id}/departments`；要求可信 Origin、当前 Session/CSRF、Idempotency-Key 与严格有界 JSON。调用已验证的同事务幂等服务；201 返回安全 DepartmentView、强 ETag 和 Location，同 Key 重放首次结果。
- Compatibility/Upgrade：冻结 `/api/v1` 不变；默认及当前 Windows 平台组合仍 404。无新 Migration/依赖；目标数据库须已升级至 `20260925_0018`。
- Tests：Windows 11/Python 3.13 后端 434/434 PASS；PostgreSQL 18 临时库真实 HTTP 首次/重放同为 201 仅一部门/Audit/快照、异载荷冲突、非负责人/跨项目 404、License 403 PASS；开发 wheel PASS。临时库已删除，测试服务已停止。
- Result：可选 HTTP PASS；Windows 平台显式组合、正式信任源、Gate 3 和可用程序包未完成。
- Known Issues：Windows Server 2025/HTTPS 与 Debian 13 本项未验证；合成许可不代表正式发行验收。
- Next：PRJ-04-A14-P03 在 Windows 显式平台组合接入部门创建并验证真实 Session。
