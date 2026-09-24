# WBS 1.05 Alembic Migration 执行报告

## 结果

`PASS / ALEMBIC_1.20.0 / POSTGRESQL_18.6 / PGVECTOR_0.8.6 / WINDOWS_11 / ZERO_BUSINESS_TABLES`

|字段|结果|
|---|---|
|Phase|Phase 1：架构冻结与基础工程|
|WBS|`1.05 Alembic migration`|
|前置|Gate 2、WBS 1.04 PASS|
|模块|`platform` ORM/Migration 基础设施|
|正式 Revision|`20260924_0001`|
|业务 ORM/Table|0 / 0|
|业务 API|0|
|客户数据外发|0|
|下一 WBS|`1.06 Error contract`|

## Changed

- 固定 Alembic 1.20.0，并沿用 SQLAlchemy 2.0.54、psycopg 3.3.5。
- 建立 `plm` Schema 的正式 ORM Base 与统一约束/索引命名约定。
- 建立随 wheel 交付的 Alembic env、revision template 和 versions package。
- 新增 `20260924_0001` 平台基线，仅固定 PostgreSQL 18 + pgvector 0.8.6。
- `plm.alembic_version` 位于应用 Schema；URL 只在内存注入，不写入 ini 或日志。
- downgrade 到 base 保留空 Schema、版本表和共享扩展，不使用 CASCADE。
- 登记 `DEC-20260924-064`；未复制 SC-04 验证性表。

## Migration 验证

|场景|结果|
|---|---|
|空库 `base → head → base`|PASS|
|有数据 `base → head → base → head`|PASS；探针记录 1/1 保留|
|Offline SQL|PASS；418 bytes|
|ORM/Migration drift|0，PASS|
|`pg_dump -Fc`|PASS；3,421 bytes|
|`pg_restore`|PASS；revision、pgvector、探针数据完整|
|downgrade 安全边界|PASS；业务表 0，保留空 `plm`/version table/pgvector|
|测试数据库清理|PASS；`wbs105_*` 全部删除，PostgreSQL 实例已停止|

## Tests

|类型|覆盖|结果|
|---|---|---|
|Migration/ORM Unit|单 head、无磁盘/离线 SQL Secret、pgvector-only revision、Schema/命名/零业务表|7/7 PASS|
|既有后端 Regression|Health、Session、UnitOfWork|25/25 PASS|
|合计|Python unittest|32/32 PASS|
|Integration|PostgreSQL 18.6 空库/有数据/恢复/漂移|PASS|
|Packaging|wheel 包含 env、template、revision 与固定依赖元数据|PASS|

## Compatibility / Upgrade

- Windows 11 x86-64、Python 3.13.15、PostgreSQL 18.6、pgvector 0.8.6 已实测。
- Windows Server 2025 与 Debian 13 本轮未运行，不扩大兼容性结论。
- 新安装由 Migration Owner 执行 upgrade；Runtime Role 不得执行 DDL 或写 `alembic_version`。

## Known Issues / Boundary

- 当前没有 65 个业务 Root 的正式 ORM/Table；它们必须按后续模块 WBS 逐项实现。
- Migration/Runtime/Maintenance 数据库角色尚未由部署脚本创建，权限实测留在对应平台/安装 WBS。
- WBS 1.09 尚未提供 Secret/配置入口，因此当前验证通过内存 Config 注入无密码的隔离测试 URL。
