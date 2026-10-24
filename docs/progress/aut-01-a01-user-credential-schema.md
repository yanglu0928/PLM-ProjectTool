# AUT-01-A01 User/Credential 存储验收

- 日期：2026-09-24；结果：PASS；来源：Gate 2 冻结提交 `64cdf09` 的 DM-02、SC-01～03、API-02 与 `DEC-20260924-075`。
- 实现：`plm.auth_users`、`plm.auth_password_credentials` 与 Alembic `20260924_0006`。包含用户名唯一、DISABLED 初始身份、当前凭据同 User/同版本复合 FK、不可变凭据历史及用户版本不倒退触发器。
- 验收：Windows 11/Python 3.13 后端 99/99；PostgreSQL 18.6 临时独立库空库 up/down/re-up、保留既有 PLT/Audit 数据升级、ORM drift=0、唯一/交叉用户/无凭据启用/版本回退/凭据不可变负例、含数据 downgrade 拒绝、备份恢复 PASS。入口：`validation/aut-01-a01-user-schema/verify.py`。
- 升级：先备份，执行 `upgrade head`；有身份数据时不能普通回退。Windows Server 2025/Debian 13 未在本任务验证。
- 遗留：用户名的 trim/NFC/casefold 尚未由应用命令生成和验证；未选定或实现真实密码哈希/验证策略，也无 Session、权限、公开 API、强制审计接线。合成测试 Hash 仅在临时测试库使用，不能作为生产认证能力。下一项为 `AUT-01-A02 User/Credential 内部命令与规范化`；Gate 3/UAT 未通过。
