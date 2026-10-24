# PLT-02-A07-P03-A04：Windows 可信时间 HMAC 密钥来源

- 日期：2026-09-25；状态：Windows 11 合成受保护来源 PASS；正式目标账户/Server 2025/生产 License 装配 NOT VERIFIED。
- Phase/WBS：Phase 2 Platform Core / PLT-02-A07-P03-A04。输入：ADR-006、LIC-03-A03 受控空初态、已实现 HMAC 完整性与 Windows 当前账户 Vault/加密备份。前置满足本项适配与验证。
- 涉及 License 完整性及 Windows 组合入口；无实体、Schema、Migration、公开 API 或权限变化。验收：独立 `trusted-time-v1` 引用解析正好 32 字节的当前账户 Vault 密钥；组合根缺钥失败；完整状态及 pristine 空初态缺钥均不被当作有效；失密后恢复原密钥可验旧状态。
- 实现：组合入口注入现有受保护 `WindowsSecretKeyProvider`，固定使用与业务 Secret 主密钥不同的 `trusted-time-v1` 引用，并在装配前强制密钥检查。运维可用已有交互入口 `secret_key_recovery provision trusted-time-v1 <绝对备份路径>` 单独供给与离线备份；切勿与业务 Secret 的 key_ref、备份或口令混用。HMAC 不接受环境变量、普通 YAML 或数据库中的密钥。
- 验证：Windows 11/Python 3.13 后端 345/345 PASS；UUID 命名临时 Vault 密钥完成 HMAC 签名→删除→拒绝→从加密备份恢复→原状态验签，临时资源已清理；合成组合入口缺钥/错误长度拒绝。wheel PASS。没有对真实可信时间状态或数据库做迁移/重置。
- 限制：真实目标账户尚未供给此密钥，异账户/Server 2025 恢复未验证。该 Vault 目标仍处于既有 `SecretKey/` 命名空间，但使用独立 ref 和独立随机材料；最终运行组合根还必须显式确保业务 Secret key_ref 与它不同。Windows 本机适配结果不能外推 Debian 13，按用户要求暂不验证。正式公钥仪式、License Guard/Secret API/发行 Gate 仍未完成。
