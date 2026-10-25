# ADR-006：License 机器绑定、Ed25519 与可信时间信任边界

## Status

`ACCEPTED_FROM_BASELINE / GATE_2_FROZEN / AMENDED_BY_CR-LIC-001`

## Date

2026-09-22

## Context

客户环境需要离线验证授权、机器绑定与有效期，同时不能把签名私钥交付到客户侧。POC-09 已验证显式 MAC 选择、规范化、SHA-256、确定性 Payload、Ed25519 验签和系统时间回拨拒绝；跨进程可信时间状态仍需形成正式端口。

## Decision

1. 机器指纹链固定为：实施人员显式选择 MAC → 大写冒号形式规范化 → SHA-256。不得自动拼接全部网卡或把原始 MAC 写入 License。
2. License Payload 使用版本化、确定性 UTF-8 序列化并由 Ed25519 私钥签名；客户运行时只包含公钥。
3. Ed25519 License 私钥和插件签名私钥只存在 Developer Workbench，不进入 Git、客户服务器、发行包、日志、数据库或客户备份。
4. 根据用户 2026-09-24 明确批准的 CR-LIC-001，第一版只为本产品提供全功能整体授权，不从七字段签名 Payload 判断多产品或细分功能权益。客户侧 `LicenseService` 验证受信任且仅供本产品发行的公钥引用、签名、Payload Schema、有效期、机器指纹和可信时间状态；任一失败均拒绝受许可业务操作。
5. `TrustedTimeStatePort` 原子保存最近成功时间和必要完整性信息；明显回拨时失败关闭并 Audit。具体表/文件字段留待 Data Model/Schema。
6. License Guard 不替代 Session、Role、Project、Resource State 和 Review Lock。
7. License 无效时只保留最小存活检查、登录以及已认证 DeploymentAdmin 的 License 查询/导入/诊断面。
8. License、机器指纹和时间错误对外只返回分类安全错误，不回显完整指纹、签名材料或内部路径。

## Consequences

- 客户侧可完全离线验签，私钥泄露面集中在 Developer Workbench。
- 显式 MAC 选择可解释、可复现，但网卡更换需要重新授权。
- 可信时间状态可发现明显回拨，但不等同于可信硬件时钟或在线时间证明。
- 首版不能按模块/功能差异化授权；公钥不得跨产品复用。变更来源：`docs/changes/CR-LIC-001-single-product-full-bundle.md`。
- License Payload、序列化或指纹规则变化需要版本兼容和迁移策略。
- 支持包和备份必须排除私钥与完整机器指纹。

## Rejected Alternatives

- 对称密钥验签：客户侧必须持有可签发材料。
- 客户侧生成 Ed25519 私钥：破坏签发信任边界。
- 自动选择任意活动网卡：虚拟网卡和顺序变化导致不可预测漂移。
- 只依赖当前系统时间：无法发现简单回拨。

## Rollback / Change Rule

Gate 2 前可细化 Payload 字段和可信时间存储实现，但不得改变 MAC → Normalize → SHA-256 → Ed25519 或私钥隔离原则。修改核心机制、允许客户侧签发或引入在线授权服务均属于 L3 安全/License 变更并需新 PoC。

## References

- `poc/poc-09-license/`
- `docs/architecture/security-file-job-runtime-boundaries-v1-candidate.md`
- `docs/progress/phase-0-summary.md`
