# LIC-03-A02 TrustedTimeStatePort 单调更新与完整性边界

- 日期：2026-09-24；结果：PASS（内部组件）；来源：Gate 2 冻结 DM-02、ADR-006、`DEC-20260924-087`。
- Changed：内部 TrustedTimeStatePort 使用 `expected_version` 和 PostgreSQL 行锁/条件 UPDATE 单调前移；HMAC-SHA256-V1 为部署级状态签出完整性元数据，密钥仅由受信任注入 Port 读取，数据库不存密钥。相同时间或允许的小幅回拨不回写；明显回拨、旧版本、缺失状态、损坏元数据或依赖失败均拒绝。成功事件/Audit 与状态同事务；拒绝事件/Audit 在回滚后独立事务保留。
- Files：`application/trusted_time.py`、`infrastructure/trusted_time_integrity.py`、`trusted_time_repository.py`、单元测试、`validation/lic-03-a02-trusted-time-port/verify.py`、决策/进度/版本说明。
- Migration：无；沿用 `20260924_0010`。API：无公开接口；Permission：端口仅供内部 LicenseService 调用，不提供客户端写路径。
- Tests：Windows 11 / Python 3.13 后端 139/139 PASS；目标组件覆盖率 97%；PostgreSQL 18.6 签出/校验、允许容差不回写、回拨拒绝、旧版本、双线程竞争、篡改元数据失败关闭和拒绝审计持久化 PASS；wheel 构建及包含检查 PASS。Windows Server 2025、Debian 13 本项未运行。
- Known Issues：生产 Secret Store 密钥解析器与首次空状态初始化尚未装配；未提供这些依赖时端口不能作为生产 License 判定。HMAC 可检测已签状态字段的单独篡改，但不是硬件时钟或在线时间证明；拥有数据库高权限者重置为初态，或数据库与密钥/备份同时回滚，无法由本端口单独识别。上层仍须先完成签名/Schema/产品/功能/机器/有效期判定，成功后才可调用此端口；Gate 3/UAT 未通过。
- Next：LIC-02-A02 LicenseService 综合验证。
