# PLT-01-A03 配置身份与持久幂等验收记录

- 日期：2026-09-24；版本：`0.1.0.dev0`（Unreleased）；结论：PASS（内部命令与事务收据，非公开配置服务）。
- 追溯：Gate 2 冻结提交 `64cdf09` → API-01 Idempotency-Key → API-02 PLATFORM_CONFIG_CREATE/CREATE_VERSION/ACTIVATE → A01～A02 配置实体与版本命令 → Alembic `20260924_0004` → 本任务验收脚本。

## 交付与决策边界

内部 `create_configuration` 只允许创建已由开发者登记非敏感策略的部署配置键，身份初态 `INACTIVE`、`lock_version=0`。与 A02 的创建版本和激活版本命令统一要求 16～128 个可打印 ASCII 字符的 `Idempotency-Key`；原始键不落库，只保存 SHA-256 摘要。规范化请求也只保存 SHA-256 指纹，不保存配置值、Secret、客户正文或请求原文。

新增 `plm.plt_configuration_command_receipts` 作为 PLT-01 命令的技术性事务收据，不新增 Aggregate Root。唯一范围为部署 Actor、Operation、Key 摘要；同键同请求在权限重新检查后返回既有结果，同键不同请求返回 `CONFLICT_IDEMPOTENCY`。收据预约、业务写入、Audit Port 和完成状态在同一数据库事务中提交；完成收据由触发器禁止 UPDATE/DELETE。跨配置/版本结果使用 FK 保护，引用列有索引。含收据数据时 downgrade 到 `0003` 失败关闭。

真实 Session、License、DeploymentAdmin、CSRF 与正式 AuditEvent 适配器尚未实现；验收中权限和 Audit 由隔离测试 Port 提供，Audit 探针写在业务同一事务。因此本任务不注册任何 `/api/v1` 管理端路由，不把测试替身描述成生产安全能力。

## 验证

- Windows 11 / Python 3.13 后端全量测试 89/89 PASS；覆盖创建、重放、冲突、非法键、未授权、Audit 失败回滚和错误码。
- Windows 11 / PostgreSQL 18.6：空库及已有数据升级、空表 down/re-up、ORM drift=0；同键并发只建一份配置；跨服务实例持久重放；同键不同请求冲突；权限拒绝、Audit 失败整笔回滚；完成收据 UPDATE/DELETE 被拒；有收据 downgrade 被拒且数据保留，均 PASS。
- A01、A02 数据库验收回归 PASS；`pg_dump`/`pg_restore` 将配置、收据和审计探针恢复至独立测试库 PASS。随机测试库在脚本结束时删除，未接触客户数据库。
- backend wheel 构建 PASS，包含配置命令、收据仓储和 `20260924_0004`。本任务无新第三方依赖、无外部客户数据传输。

## 升级、兼容与已知问题

部署前备份 PostgreSQL 18，执行 Alembic `upgrade head`（`0003` → `0004`）。已有命令收据时不能直接 downgrade；须先按正式恢复流程处理。Windows 11 已验证；Windows Server 2025、Debian 13 未在本任务验证。收据目前保留至后续正式 Retention 策略实施；Runtime 数据库角色还需按冻结安全基线限制 DDL/TRUNCATE 权限。

PLT-01 Settings/Retention 子表、真实 Auth/License/CSRF/AuditEvent、默认可用配置策略和公开管理 API 均未交付。下一阶段优先建设 Phase 2 AuditEvent 持久层，再接入真实授权及配置 API；在这些边界完成前配置服务不可供客户使用。
