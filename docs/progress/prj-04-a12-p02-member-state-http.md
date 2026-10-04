# PRJ-04-A12-P02：成员状态命令可选 HTTP

- Phase/WBS：Phase 2 Platform Core / PRJ-04-A12-P02。来源：冻结 API-01/02、PRJ-02-A04、PRJ-04-A12-P01；决策 DEC-20260925-073。
- Changed：新增仅显式注入时挂载的 SUSPEND/RESUME/REMOVE 三个 POST 路由；要求可信 Origin、有效 Session/CSRF、Idempotency-Key、强 If-Match 和空正文。调用已验证的同事务持久幂等服务；返回安全 MemberView 与 ETag，同 Key 重放首次结果，不重复写入或 Audit。
- Compatibility/Upgrade：冻结 `/api/v1` 路径和响应语义不变；默认及当前平台组合仍为 404。无新 Migration/依赖；目标数据库须已升级至 `20260925_0017`。
- Tests：Windows 11/Python 3.13 后端 421/421 PASS；PostgreSQL 18 临时库三个状态真实 HTTP 首次/重放、异载荷冲突、跨项目 404、License 403、既有并发/历史/迁移/回滚验证 PASS；开发 wheel PASS。临时库已删除，测试服务已停止。
- Result：可选 HTTP 接口 PASS；Windows 平台显式组合、正式信任源、Gate 3 和可用程序包未完成。
- Known Issues：Windows Server 2025/HTTPS 与 Debian 13 本项未验证；不能把合成 License 验证视为正式发行验收。
- Next：PRJ-04-A12-P03 在 Windows 显式平台组合接入状态命令并做真实 Session 的隔离 PostgreSQL 验证。
