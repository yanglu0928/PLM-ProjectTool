# LIC-02-A02：LicenseService 综合验证

- 日期：2026-09-24；结果：PASS（内部服务）；基线：V2.1 + 用户批准 CR-LIC-001、ADR-006、DM-02、`DEC-20260924-089`。
- Changed：保留原 `plm.license.v1` 七字段签名 Payload，不增加产品/功能字段。内部服务只从受信任产品公钥 Port 取引用，从实施人员选定 MAC Port 取本机 MAC，从 Clock Port 取 UTC 时间；先 Ed25519 验签，再严格字段/时间窗/指纹比对，最后调用 TrustedTimeStatePort。成功结果明确为本产品全功能整体授权候选，非已激活 License。
- Files：`license_validation.py`、单元测试、`validation/lic-02-a02-license-service/verify.py`、决策/进度/版本说明。Migration：无。API：无公开接口。Permission：信任输入均由内部 Port 注入，不接受客户端公钥或 MAC；真实 DeploymentAdmin 权限须在后续导入命令中校验。
- Tests：Windows 11/Python 3.13 后端 144/144、POC-09 回归 26/26 PASS，LicenseService 目标覆盖率 91%；PostgreSQL 18.6 临时库中真实合成 Ed25519 签名、七字段 Schema、选定 MAC、有效期、可信时间前移与错机器/旧版本/回拨负例 PASS；wheel 构建和模块包含 PASS。Windows Server 2025、Debian 13 本项未运行。
- Known Issues：本项不写 `LicenseValidationState`、不导入或激活安装；一般验证拒绝的持久审计留给下一编排任务。生产本产品专用公钥、人工选定 MAC 配置、可信时间 HMAC 密钥解析及一次性初始化尚未接线；不能据此开放业务或通过 Gate 3/UAT。当前单产品全功能，不支持分级功能授权。
- Next：LIC-02-A03 验证结果持久化与审计编排。
