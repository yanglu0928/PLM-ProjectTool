# PLT-02-A07-P03-A05：Windows License 生产组合根

- 日期：2026-09-25；状态：Windows 11 合成端到端与真实 PostgreSQL 组合 PASS；正式发行信任锚/目标账户密钥 NOT VERIFIED。
- Phase/WBS：Phase 2 Platform Core / PLT-02-A07-P03-A05。输入：Gate 2/ADR-006、CR-LIC-001、LIC-01～03 内部服务、P03-A01 本机 MAC、P03-A02 包内公钥、P03-A04 独立 Vault 可信时间密钥和现行 Migration。代码前置满足。
- 涉及 Windows 入口组合与验证脚本；无实体、Schema、Migration、公开 API 或权限变更。验收：仅真实包内本产品公钥、本机选定 MAC、当前账户独立 Vault 密钥和现行 PostgreSQL Schema 可用于生产装配；缺项失败关闭；合成隔离条件下 Guard 完整链可执行。
- 实现：`create_windows_license_services` 检查数据库可用和 Schema head，然后解析包内公钥、验证本机 MAC、要求可信时间密钥可用，装配真实 `LicenseService`、`TrustedTimeStatePort`、`LicenseRuntimeGuard` 与 SQLAlchemy/Audit。组合入口不读取请求、普通配置或数据库中的替代公钥；不生成密钥、不挂载公开路由。
- 验证：Windows 11/Python 3.13 后端 348/348 PASS；临时 PostgreSQL 18.6 数据库升至当前 head，在真实本机 MAC、临时 Vault HMAC 密钥、进程内合成 Ed25519 签名/公钥下，未安装拒绝、有效完整 License 通过、删除密钥后 Guard 拒绝并持久记录 `TRUST_STATE_INVALID` PASS；临时数据库、Vault 条目与备份清理，PostgreSQL 服务已停止。wheel 构建 PASS。
- 限制：测试显式注入合成公钥，仅用于验证依赖接线；当前默认生产入口因包内正式公钥不存在而失败，不宣称 License 正式可用。真实 Developer Workbench 密钥仪式、公钥清单、目标账户可信时间密钥/独立恢复、Server 2025、HTTPS 代理和公开 License/Secret API 仍未完成；Debian 13 按用户指令暂不验证。Gate 3/UAT/Release 未通过。
