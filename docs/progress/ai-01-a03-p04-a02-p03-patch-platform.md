# AI-01-A03-P04-A02-P03 Provider PATCH Windows 平台装配

日期：2026-10-02；状态：Windows 11 隔离合成验证 PASS；决策：DEC-20261002-637。

## 编码前检查

|项目|结论|
|---|---|
|当前Phase|Phase 2 Platform Core，Gate 2 已批准；Gate 3 未通过|
|当前WBS|AI-01-A03-P04-A02-P03|
|输入基线|冻结 API-01/API-03 Provider PATCH；`AI-01-A03-P04-A02-P02` 可选 PATCH HTTP；CR-AI-001 增量 Schema 0054|
|前置任务|内部部分 PATCH、可选 HTTP、Windows 显式写组合与 Provider 创建均已验证并同步|
|涉及模块|Windows 生产组合根与 AI Provider API 接线|
|涉及实体|AIProvider、AIProviderConfigVersion；无实体/Schema 更改|
|涉及API|现有 `PATCH /api/v1/admin/ai/providers/{provider_id}`；仅改变显式写组合可达性|
|涉及权限|部署管理员、当前 Session/CSRF、License、Secret 证明、强 If-Match；不放宽|
|验收标准|默认/登录 404、只读平台 405、写平台真实 PG/ASGI 200/ETag/重放/权限与 License 拒绝；写依赖失败关闭；全量后端与 wheel|
|风险|正式信任源尚未供给；旧平台合成游标钥脚本需独立维护；不得宣称生产/Gate PASS|

## 结果与边界

- Changed/Files：仅生产组合根显式写分支注入现有 PATCH Router，增加组合失败关闭合同、隔离 PG/ASGI 脚本；冻结 API/实体不变。
- Migration/API：无新迁移；现有 PATCH 只在 `--platform-write` 可达；默认/登录模式 404，只读 `--platform` 405。
- Tests：生产组合合同 30 项通过；隔离 PostgreSQL 18 / ASGI 真实 Session 创建→PATCH→GET、ETag、同 Key 原结果重放、异载荷/旧版本409、普通用户404、合成 License 403、审计单条及只读边界通过；后端全量 1932 运行/3 跳过；开发 wheel 构建通过，SHA-256 `7adf3fd729dc3e91213e527d1de74d3da6ed2254f63ed3df23d2bc6e13d453f9`。本地测试集群恢复停止状态。
- 兼容/升级/回滚：兼容已有 Schema 0054、无新依赖或 Breaking API。部署须先正式供给目标账户数据库、License、Secret 和游标钥信任源；撤该组合注入可代码回滚，不删除历史配置/收据/审计。
- Known Issues：正式发行信任锚、Server 2025/Debian、质量 Gate、完整 UAT 和可用程序包未验；39 份历史平台合成游标夹具尚未回归。当前合成证据不等于生产就绪。
