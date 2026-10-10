# PLT-02-A07-P05-A06：Secret 轮换 write-only HTTP

- Phase/WBS：Phase 2 Platform Core / PLT-02-A07-P05-A06。输入：冻结 API-01/API-02、P05-A01 记录锁版本、P05-A02 强 If-Match、P05-A04 持久幂等、P05-A05 Secret JSON 安全边界。代码前置满足可选路由；生产主密钥/License 信任锚仍缺。
- Changed：新增显式注入的 `POST /api/v1/admin/secrets/{secret_id}:rotate`；可信 Host/Origin、唯一 Cookie/CSRF/Idempotency-Key、现行 Session 后解析单个强 If-Match 为记录锁版本。请求仅接受有界非空 UTF-8 `secret_value`；200 仅返回 SecretRef、ACTIVE、新密文版本号、强 ETag 和 TraceId。重放复用原语义，无值/密文回显；可变明文字节清零。默认/当前 Windows 生产组合不挂载。
- Files：轮换 API、共用安全 JSON/错误映射、应用工厂、契约及 PostgreSQL HTTP 验证、决策/状态/版本记录。
- Migration：无；复用现有 Secret Schema 和通用收据 `0015`。API：实现已冻结轮换路径的可选 Router，无 Breaking Change。
- Tests：Windows 11/Python 3.13 后端 373/373 PASS；缺 If-Match 428、弱/复合 400、陈旧 409、Session/正文脱敏/默认 404；PostgreSQL 18 临时库 HTTP→真实写服务→新密文版本/审计/收据，同 Key 两次 200 仅一条新版本与一次轮换 Audit PASS；开发 wheel PASS。临时库已删除，数据库服务停止。
- Result：可选 HTTP 与隔离合成端到端 PASS；正式生产装配未完成，PLT-02-A07/Gate 3 未通过。
- Known Issues：JSON 解码短生命周期不可原地清零字符串风险继承 P05-A05 控制；停用 HTTP、生产主密钥/License、Server 2025/异账户及 Debian 13 未验证。
- Next：PLT-02-A07-P05-A07 Secret 停用 HTTP，随后正式写组合与发行前安全验收。
