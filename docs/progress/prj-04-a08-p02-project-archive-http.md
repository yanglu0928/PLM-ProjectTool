# PRJ-04-A08-P02：Project 归档 HTTP 边界

- Phase/WBS：Phase 2 Platform Core / PRJ-04-A08-P02。输入：冻结 `PROJECT_ARCHIVE`、P01 同事务幂等、当前 Session/License/权限；决策 `DEC-20260925-061`。
- Changed：新增仅显式注入的 `POST /api/v1/projects/{project_id}:archive`；可信 Origin、Cookie Session、CSRF、Idempotency-Key、强 If-Match 与空正文保护；200 返回安全 ProjectView/ETag。不同指纹 Key 409，默认及当前平台组合仍不挂载。
- Files：Project 归档 Router、应用可选装配、HTTP 契约/临时库验证、决策/状态/版本记录。
- Migration：无；需已有 `0015`。API：符合冻结 `/api/v1` 合同，无 Breaking Change。
- Tests：Windows 11/Python 3.13 后端 398/398 PASS；PostgreSQL 18 临时库 HTTP 同 Key 重放仅一次归档/Audit、异版本 409；P01 内部并发与回滚仍 PASS；开发 wheel 构建 PASS。临时库已删除，数据库服务停止。
- Result：可选 HTTP 和隔离合成端到端 PASS；Windows 显式平台组合、PRJ-04 整体、Gate 3 和可用程序包未完成。
- Known Issues：正式发行信任源、Server 2025/HTTPS、Debian 13 未验证；归档后其他模块新写/Job 的拒绝仍需逐模块验收。
- Next：PRJ-04-A08-P03 接入 Windows 显式平台并验证真实 Session/数据库与合成 License。
