# WBS 1.05 Alembic Migration Validation

状态：`WINDOWS_11 / POSTGRESQL_18 / PGVECTOR_0.8.6 / FORMAL_BASELINE / ZERO_BUSINESS_TABLES`

本验收验证正式 Alembic 基础工程，不复制 SC-04 验证性 Schema：

- ORM Base 固定 `plm` Schema 与约束命名约定，当前业务表为 0；
- `plm.alembic_version` 位于应用 Schema；
- 首个正式 revision 固定 PostgreSQL 18 与 pgvector 0.8.6 平台基线；
- 空库 `base → head → base`；
- 带独立探针数据的 `base → head → base → head`，数据保持；
- ORM/Migration 漂移为 0；
- `pg_dump -Fc` / `pg_restore` 恢复后 revision、扩展和探针数据完整；
- downgrade 到 base 后保留空 `plm` Schema、版本表和共享 pgvector 扩展。

运行脚本需要已有的 PostgreSQL 18 测试实例与 pgvector 0.8.6 扩展文件。脚本创建并最终删除三个 `wbs105_*` 测试数据库，不接触客户数据。

```powershell
python validation/wbs-1.05-alembic-migration/verify.py --host 127.0.0.1 --port 55432 --user poc_admin --pg-bin D:\POC-02\postgresql-18.6\pgsql\bin --write
```

结构化结果写入 `evidence/windows-11/result.json`；数据库 dump 只存在于临时目录，不提交仓库。
