# LIC-01-A01 LicenseInstallation 存储验收

- 日期：2026-09-24；结果：PASS；来源：Gate 2 冻结 DM-02/SC-01～03、ADR-006、`DEC-20260924-083`。
- 实现：`plm.lic_installations` 与不可变签名文档子表；公钥引用、签名文档快照/摘要、安装与验证状态引用。私钥和原始 MAC 不建列；数据库限制单一 ACTIVE、状态流转、文档不可改、历史不可删。
- 验收：Windows 11/Python 3.13 后端 126/126、wheel 构建 PASS；PostgreSQL 18.6 临时独立库空库 up/down/re-up、已有用户升级、ORM drift=0、状态/唯一/文档约束、非空回退拒绝、含 ACTIVE 历史备份恢复 PASS。入口：`validation/lic-01-a01-installation-schema/verify.py`。
- Migration：`20260924_0008`；升级前备份，执行 `upgrade head`。有 License 安装/文档记录时普通 downgrade 拒绝。API：无新增公开路由。Windows Server 2025/Debian 13 本任务未验证。
- 遗留：本项仅验证存储，脚本使用合成的无效签名文档；真实签名/机器/时间验证、TrustedTimeState、LicenseService、导入/激活权限与 Audit 尚未实现，不能把 ACTIVE 测试行视为有效授权。Gate 3/UAT 未通过。
