# WBS 1.04 SQLAlchemy Session 执行报告

## 结果

`PASS / SQLALCHEMY_2.0.54 / PSYCOPG_3.3.5 / POSTGRESQL_18.6 / WINDOWS_11 / NO_ORM_TABLES / NO_MIGRATION`

|字段|结果|
|---|---|
|Phase|Phase 1：架构冻结与基础工程|
|WBS|`1.04 SQLAlchemy session`|
|前置|Gate 2、WBS 1.02 PASS|
|模块|`platform` Application / Infrastructure|
|实体/业务 ORM|0|
|数据库对象/Migration|0；不适用|
|业务 API|0|
|权限|数据库 Runtime/Migration 角色分离边界保留；本任务未创建角色|
|客户数据外发|0|
|下一 WBS|`1.05 Alembic migration`|

## Changed

- 固定 SQLAlchemy 2.0.54 与 psycopg 3.3.5，复用 Phase 0 和 SC-04 已验证版本。
- 新增技术无关 `UnitOfWork` Application Protocol；Application 层不导入 SQLAlchemy。
- 新增 `DatabaseRuntime`，统一 Engine Pool、readiness 和安全 URL。
- 新增一次性 `SqlAlchemyUnitOfWork`：独立 Session、显式事务、默认回滚、退出关闭。
- 固定 `READ COMMITTED`、pool pre-ping、return rollback、连接/池超时与 recycle。
- 只接受 `postgresql+psycopg`；不读取 Secret 文件，不创建 ORM Table 或 Migration。
- 登记 `DEC-20260924-063`。

## Tests

|类型|覆盖|结果|
|---|---|---|
|Unit/Config/Security|驱动/数据库名/池参数校验、密码隐藏、非活动 Session、readiness 失败关闭|6/6 PASS|
|Unit/Transaction|显式提交、默认回滚、异常回滚、显式回滚、单次使用、会话隔离、begin 失败关闭|7/7 PASS|
|Regression|WBS 1.02 Health/App Factory|12/12 PASS|
|合计|Python unittest|25/25 PASS|
|Live integration|PostgreSQL 18.6、双连接、READ COMMITTED、application_name、readiness、Session 关闭|PASS|
|Static boundary|Application 无 ORM 依赖；业务 ORM/Migration/API 数量|PASS；0/0/0|
|Packaging|Python 3.13 wheel build|PASS|

实连验收使用隔离的本机 PostgreSQL 18.6 PoC 实例，只执行只读查询和事务控制；未创建持久对象，测试结束后实例已停止。

## Compatibility / Upgrade

- Windows 11 x86-64、Python 3.13.15、PostgreSQL 18.6 已验证。
- Windows Server 2025 本轮未重跑；沿用 Phase 0 数据库可行性证据但不扩大本轮结论。Debian 13 未验证。
- 升级仅新增 Python 依赖与代码；无数据库升级步骤。正式 Schema 从 WBS 1.05 开始。

## Known Issues / Boundary

- 当前 Composition Root 尚未从 WBS 1.09 Config/Secret 创建并释放 `DatabaseRuntime`，因此 app factory 默认仍不连接数据库。
- 同步 Session 不得在 async 事件循环中直接执行阻塞 I/O；后续端点使用同步依赖/执行边界。
- 正式 Runtime/Migration 数据库角色、`plm` Schema、ORM 和 Alembic revision 尚未创建。
