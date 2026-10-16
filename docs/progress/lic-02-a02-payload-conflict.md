# LIC-02-A02：License Payload 冻结冲突（L3，已批准方案 B）

- 日期：2026-09-24；状态：RESOLVED_BY_CR-LIC-001；冲突发现时尚未编码，后续实施以正式 CR 为准。
- 证据一：`PLM项目实施辅助工具软件开发实施方案 V2.1.md` §1.18 明列签名 Payload 为 `license_id/customer/machine_fingerprint/valid_from/valid_to/issue_time/schema_version` 七字段；POC-09 的 `plm.license.v1` 对字段集合严格校验。
- 证据二：冻结 ADR-006 第 4 条要求 LicenseService 验证产品/功能；冻结 DM-02 的 `entitlement_snapshot` 也包含受许可产品/功能/有效期。
- 冲突：当前七字段没有签名保护的产品/功能权益，不能从中真实判定目标产品或细分功能许可。静默增加字段会改变既有签名 Payload/序列化及版本契约，属于 L3 安全/License 核心机制和已锁定方案变更。
- 方案 A（建议）：用户明确批准修改已锁定方案，为新的签名 Payload 版本增加受控 `product_code` 与 `features` 字段；定义与 v1 的兼容/拒绝策略，另行冻结变更后再实现。既有 PoC v1 仅作历史技术验证，不自动具备新版产品/功能权益。
- 方案 B：维持七字段，明确将首版 License 限于单一产品、全部功能整体授权，并相应修改冻结 ADR/DM 对细分产品/功能验证的要求。此方案削弱已冻结的权益边界，同样必须 L3 批准。
- 结论：用户明确回复“明确同意修改已锁定方案，采用方案B”。正式范围和兼容性见 `docs/changes/CR-LIC-001-single-product-full-bundle.md`；方案 A 未采用。
