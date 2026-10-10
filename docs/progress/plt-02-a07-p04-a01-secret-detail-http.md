# PLT-02-A07-P04-A01：Secret 元数据详情只读 HTTP

- Phase/WBS：Phase 2 Platform Core / PLT-02-A07-P04-A01。输入：冻结 API-01/API-02、PLT-02-A03 内部管理员安全投影、AUT-03 Session/Origin、现行 License Guard。上述前置满足本项可选只读 HTTP 开发；生产装配前置仍未满足。
- Changed：新增显式注入的 `GET /api/v1/admin/secrets/{secret_id}`，可信 Host/Origin、严格 Cookie、现行 Session、内部 DeploymentAdmin 和 License 双重校验；仅返回非敏感元数据与基于 `lock_version` 的强 ETag。管理员权限不足和目标不存在均返回 404；内部/许可源异常失败关闭。默认应用保持 404。
- Files：Platform Secret API、元数据 View/SQL 投影、应用工厂、单元与契约测试、决策/状态/版本记录。
- Migration：无；只读取现有 `lock_version`，无 Schema 变动。
- API：冻结路径的只读详情一项；列表、创建、轮换、停用尚未公开，不改变 `/api/v1` 合同。
- Tests：Windows 11/Python 3.13 后端 351/351 PASS；可选挂载、默认 404、安全投影/ETag、Host/Cookie/Session、权限/缺失/不可用分支覆盖；开发 wheel 构建 PASS。后续 P04-A02 复验 PostgreSQL 18 临时库活动锁版本 1、停用版本 2、安全投影 PASS。
- Result：本项代码与合成契约验证 PASS；未进行真实目标账户/正式 License/Secret 管理装配验证，不等于 PLT-02-A07 整体 PASS。
- Known Issues：正式签发公钥与目标账户可信时间密钥未供给；Server 2025/异账户和 Debian 13 未验证；列表需要完整不透明游标，写接口需要 If-Match、幂等、审计及密钥恢复演练。
- Next：PLT-02-A07-P04-A02 Secret 元数据列表安全游标，或优先完成独立的生产组合前置；不得提前公开写接口。
