# PLT-02-A07-P05-A05：Secret 创建 write-only HTTP

- Phase/WBS：Phase 2 Platform Core / PLT-02-A07-P05-A05。输入：冻结 API-01/API-02、AUT-03 Session/CSRF、PLT-02-A05 创建/审计及 P05-A03 持久幂等。代码前置满足可选路由；正式主密钥/License 信任锚未供给，生产挂载前置未满足。
- Changed：新增显式注入的 `POST /api/v1/admin/secrets`。可信 Host/Origin、唯一 Cookie/CSRF/Idempotency-Key 与现行 Session 先验证；最多 70,000 字节 JSON，精确 `purpose`、`allowed_consumer`、`secret_value` 三字段，拒绝重复键/非标准常量/未知字段；受控用途/消费者及 1～65,520 字节 UTF-8 值。响应 201 仅 SecretRef、强 ETag、Location、TraceId，不回显值/密文；可变明文字节清零。默认应用和当前 Windows 平台组合仍不挂载。
- Files：Platform Secret 创建 API/错误码/应用工厂、契约测试、PostgreSQL HTTP 端到端验证、决策/版本/状态记录。
- Migration：无；复用既有通用幂等收据 `0015`。API：实现已冻结创建路径的可选 Router，无 Breaking Change。
- Tests：Windows 11/Python 3.13 后端 370/370 PASS，Host/Origin/Session/CSRF/Key、严格体积/JSON/枚举、失败脱敏与默认 404；PostgreSQL 18 临时库中 HTTP→真实内部写服务→密文/审计/收据，同 Key 201 重放仅一次 Secret/审计 PASS；开发 wheel PASS。临时库已删除，数据库服务已停止。
- Result：可选 HTTP 契约与隔离合成端到端 PASS；正式生产主密钥/License/目标账户缺失，不能标公开生产写接口 PASS。
- Known Issues：Python JSON 解码期间会短暂产生不可原地清零的字符串；请求体受限、不记录，服务及 API 可变字节清零。轮换/停用 HTTP、生产写组合、Server 2025/异账户与 Debian 13 未验证。
- Next：PLT-02-A07-P05-A06 Secret 轮换 write-only HTTP，随后停用 HTTP 和正式生产装配验收。
