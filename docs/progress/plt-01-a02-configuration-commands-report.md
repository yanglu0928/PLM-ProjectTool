# PLT-01-A02 配置版本命令与仓储边界验收记录

- 日期：2026-09-24；版本：`0.1.0.dev0`（Unreleased）；阶段：Phase 1。
- 结论：PASS（内部版本命令与仓储；不代表管理 API 或生产 Audit/认证已就绪）。
- 追溯：Gate 2 冻结提交 `64cdf09` → DM-02 SystemConfiguration → API-02 PLATFORM_CONFIG_CREATE_VERSION/ACTIVATE → SC-02 Version Profile → A01 revision `20260924_0002` → A02 revision `20260924_0003`、命令与验收脚本。

## 交付

增加开发者拥有的非敏感配置值精确白名单策略。未知键、敏感命名空间、未列入策略的值、类型不符、Schema 版本不符和超过限额的值默认拒绝；值不进入命令对象 `repr` 或 Audit 投影。当前不随产品启用任何默认策略，必须由后续 Composition Root 显式登记并审核，不能从客户请求动态注册策略。

内部 `create_version` 在锁定配置主记录后计算单调版本号、同父 supersedes、内容指纹和乐观锁更新；`activate_version` 仅更改主记录 Active 指针，不覆写不可变版本。两个命令均要求注入的 Deployment 写权限 Port 和同事务 Audit Port；任一 Port 缺失、拒绝或失败均不提交业务写入。授权 Port 契约要求有效 Session、License 与 DeploymentAdmin；本任务未实现这些生产适配器。Audit 测试使用同一事务中的隔离探针表，不冒充正式 AuditEvent。

API-02 要求配置值携带 `schema_version`。A01 已发布迁移未改写；新迁移 `20260924_0003` 为不可变版本补齐正整数 `schema_version` 列，旧数据安全归为 1。回退到 `0002` 只允许全部版本仍为 1，含非初始 Schema 版本时失败关闭。版本内容仍由数据库触发器禁止 UPDATE/DELETE。

## 验证

- Windows 11 / Python 3.13 后端全量测试 85/85 PASS；覆盖策略白名单、冻结平台错误码、错误脱敏、权限拒绝、并发版本冲突和 Audit 失败回滚。
- Windows 11 / PostgreSQL 18.6：旧 `0002` 有数据升级到 `0003`、空库及有数据 down/re-up、非初始 Schema 版本拒绝回退、ORM drift=0 PASS。
- 真实仓储创建、激活、两笔并发争用同一配置只接受一笔、Audit 失败时版本与主记录一同回滚、未授权写入拒绝 PASS；A01 数据库验收重跑 PASS。隔离随机测试库测试后删除，未触及客户库。
- backend wheel 构建及领域、命令、仓储、迁移四个文件内容检查 PASS。

## 兼容、升级、已知问题

部署前备份 PostgreSQL 18，执行 Alembic `upgrade head`（`20260924_0002` → `20260924_0003`）。Windows 11 已验证；Windows Server 2025、Debian 13 本任务未验证。无公开 API、客户资料外发或新第三方依赖。

本任务不含配置身份创建、持久幂等记录、真实 Session/License/DeploymentAdmin 适配器、正式 AuditEvent 存储、CSRF、管理端 API/页面或客户可用默认配置策略；在这些边界完成前不得将内部命令暴露给客户端。A01 `version_state='ACTIVE'` 在此表示版本可用性，当前生效版本只以主记录指针判定。下一任务应先补齐配置身份与幂等命令，再接入真实授权/Audit 和冻结 API。
