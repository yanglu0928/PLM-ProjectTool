# PRJ-04-A04：Project 创建 HTTP

- Phase/WBS：Phase 2 Platform Core / PRJ-04-A04。输入：冻结 API-01/API-02 `PROJECT_CREATE`、PRJ-01-A04 内部原子创建、PRJ-04-A03 同事务幂等、Auth Session/CSRF 与可信 Host/Origin；决策 `DEC-20260925-056`。
- Changed：新增仅显式注入的 `POST /api/v1/projects`。先校验可信来源、唯一 Cookie/CSRF/Idempotency-Key 与现行 Session，再解析不超过 8 KiB 的 UTF-8 JSON；拒绝重复键、非标准常量、未知字段、非 canonical UUID 和非法部门 seed。调用已验证的幂等创建服务。201 仅返回冻结 ProjectView、强 ETag、Location/TraceId；不暴露首位成员内部 ID、SQL 或 traceback。默认/当前生产组合未挂载。
- Files：Project API、应用工厂、错误注册、契约/临时 PostgreSQL HTTP 验证、决策/状态/版本说明。
- Migration：无；目标库需已有通用收据 `0015`。API：实现冻结创建路径的可选 Router，无 Breaking Change。
- Tests：Windows 11/Python 3.13 后端 390/390 PASS；默认 404、201 安全投影、Origin/CSRF/Key/JSON/UUID 拒绝、License/管理员/冲突错误；PostgreSQL 18 临时库 HTTP 同 Key 两次 201 仅一 Project/Audit、非管理员 404、License 403 PASS；开发 wheel 构建 PASS。临时库已删除，数据库服务停止。
- Result：可选 Project 创建 HTTP 与隔离合成端到端 PASS；正式 Windows 平台组合、发行信任源、PRJ-04 整体/Gate 3 未完成。
- Known Issues：正式 License 签发、目标账户密钥、Server 2025/HTTPS 与 Debian 13 未验证；不能据此接受真实客户项目创建。
- Next：PRJ-04-A05 将 Project 创建安全接入显式 Windows 平台组合，并验证缺信任源失败关闭。
