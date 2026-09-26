# PLT-01-A01 SystemConfiguration ORM/Migration 验收记录

- 日期：2026-09-24；版本：`0.1.0.dev0`（Unreleased）；阶段：Phase 1。
- 结论：PASS（仅配置身份与不可变版本持久层；不是完整 PLT-01 或生产配置服务）。
- 追溯：Gate 2 冻结提交 `64cdf09` → DM-02 SystemConfiguration → SC-01 PLT-01 物理映射 → SC-02 M-DEP/Version 约束 → `20260924_0002` → 本任务验收脚本。

## 变更与边界

`plm.plt_system_configurations` 实现部署唯一命名空间键、ACTIVE/INACTIVE 状态、UUIDv7 身份、创建/更新与乐观锁字段、保留策略引用占位和同一配置的 Active Version 指针。`plm.plt_configuration_versions` 实现 UUIDv7、父配置、正整数版本号、不可变值与 SHA-256 长度指纹、同父 supersedes 引用及复合唯一约束。数据库拒绝跨配置 Active 指针、错误 JSON 值形状、版本 UPDATE/DELETE。FK 默认 NO ACTION、非延迟。版本值仅限非敏感配置；Secret、密码、Token、License 私钥及客户正文不能进入该聚合。

本任务未实现配置命令、单调版本分配、敏感值识别、DeploymentAdmin 授权、Audit、PLT-01 Settings/RetentionPolicy/RetentionHold 子表或 PLT-02 SecretRecord。这些行为须在对应后续 WBS 完成并验收前保持不可通过业务 API 使用。`retention_policy_id` 目前无目标表 FK，待 RetentionPolicy 子表落地时补充，不宣称保留策略已可用。

## 验证

- Windows 11 / Python 3.13 后端全量回归 72/72 PASS；离线 upgrade SQL 脱敏测试 PASS。
- Windows 11 / PostgreSQL 18.6 / pgvector 0.8.6：独立随机测试库空库 up/down/re-up PASS；既有表数据升级后保留 PASS；ORM 对迁移后 `plm` Schema drift=0。
- 负例：跨配置活动指针、不可变版本 UPDATE/DELETE、值类型不符全部被数据库拒绝；含配置数据 downgrade 拒绝且数据保留；空配置表 downgrade PASS。
- `pg_dump`/`pg_restore` 到独立测试库，版本与既有数据恢复 PASS。测试库由验证脚本创建并在结束时删除；未触及客户数据库。
- backend wheel 构建 PASS；打包内容包含 `configuration_orm.py` 与 `20260924_0002_plt_configuration.py`。

## 兼容、升级、回退与已知问题

目标仍为 Windows 11、Windows Server 2025、Debian 13 x86-64；本任务只实测 Windows 11，其他平台未验证。部署前备份数据库，并在 PostgreSQL 18 上执行 Alembic `upgrade head`（`20260924_0001` → `20260924_0002`）。已有配置数据时禁止直接 `downgrade`；须先按正式恢复流程备份/迁移数据。生产数据回退未执行，不能视作已验证。当前无公开 API 或客户数据外发。

下一任务：`PLT-01-A02` 配置版本命令与仓储边界，落实非敏感值校验、单调版本分配、乐观并发、权限与 Audit 的分阶段交付；不在本任务假定这些能力已完成。
