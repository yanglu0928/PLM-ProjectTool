# PLT-02-A07-P05-A07：Secret 停用 HTTP

- Phase/WBS：Phase 2 Platform Core / PLT-02-A07-P05-A07。输入：冻结 API-02、现行 Session/CSRF/可信来源、P05-A02 强 If-Match、P05-A04 同事务幂等及内部停用服务。正式生产主密钥和 License 信任锚未供给。
- Changed：新增仅显式注入的 `POST /api/v1/admin/secrets/{secret_id}:disable`。先验证可信 Host/Origin、唯一 Cookie/CSRF/Idempotency-Key 与 Session，再解析强 If-Match；请求体必须为空。200 只返回 SecretRef、DISABLED、空当前版本、强 ETag 和 TraceId；默认及当前生产组合不挂载。
- Files：停用 API、应用工厂、契约测试、PostgreSQL HTTP 验证、决策/状态/版本说明。
- Migration：无；复用 Secret Schema 与通用收据 `0015`。API：实现冻结路径的可选 Router，无 Breaking Change。
- Tests：Windows 11/Python 3.13 后端 376/376 PASS；默认 404、缺/弱 If-Match、非空正文、失效 Session、陈旧版本拒绝；PostgreSQL 18 临时库 HTTP→真实写服务，同 Key 两次 200 仅一次停用/Audit，密文读取失败关闭 PASS；开发 wheel 构建 PASS。临时库已删除，数据库服务停止。
- Result：可选 HTTP 与隔离合成端到端 PASS；正式生产装配未完成，PLT-02-A07/Gate 3 未通过。
- Known Issues：正式主密钥/License、目标运行账户、Windows Server 2025/异账户恢复和 Debian 13 未验证。
- Next：PLT-02-A07-P05-A08 评估正式写装配的安全前置，仍不得以合成信任源开放生产写路由。
