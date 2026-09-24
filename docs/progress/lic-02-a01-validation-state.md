# LIC-02-A01 LicenseValidationState 存储验收

- 日期：2026-09-24；结果：PASS；来源：Gate 2 冻结 DM-02/SC-01～03、ADR-006、`DEC-20260924-085`。
- 实现：`plm.lic_validation_states` 部署单例与追加不可变 `plm.lic_validation_events`；VALID 必需安装/事件/指纹/权益/时间形状，状态版本单调更新。安装记录的验证结果引用增加真实外键；验证事件的安装 ID 为来源引用，避免双向 FK 循环。
- 验收：Windows 11/Python 3.13 后端 132/132、wheel 构建 PASS；PostgreSQL 18.6 临时库空库 up/down/re-up、已有安装升级、旧脏引用升级前拒绝、ORM drift=0、单例/VALID 形状/不可变事件/状态版本约束、非空回退拒绝和含验证历史恢复 PASS。入口：`validation/lic-02-a01-validation-state/verify.py`。
- Migration：`20260924_0009`；升级前备份并执行 `upgrade head`。如已有 LIC-01 手工写入的非空 `validation_result_ref`，需先受控核对，迁移会拒绝无来源引用；有验证历史时普通 downgrade 拒绝。API：无新增公开路由。Windows Server 2025/Debian 13 本任务未验证。
- 遗留：本项只验证存储形状，测试中合成 VALID 行不代表有效 License。签名、机器、产品/功能、可信时间、安装来源与事件一致性、导入/激活/Audit 须由 LicenseService 验证；Gate 3/UAT 未通过。
