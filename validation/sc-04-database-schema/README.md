# SC-04 Database Schema Validation

状态：`VALIDATION_ONLY / NOT_PRODUCTION_SCHEMA / NOT_GATE_2_FROZEN`

该工作区验证 SC-01～SC-03 的 PostgreSQL 18/Alembic 机制：

- 65 个 Aggregate Root primary table 名称、PK 与 Profile 覆盖；
- `plm` Schema、uuidv7、Scope/ProjectId、复合 FK、唯一/CHECK 与 append-only；
- B-tree、partial unique、GIN、HNSW 和关键查询计划；
- 空库与有数据 Alembic up/down；
- Job `SKIP LOCKED`、Lease/幂等、Retention/Hold、备份恢复和敏感字段扫描。

它不是正式业务 Schema。未被代表性细化的 Root 只按 M/V/A/R/SEC Profile 建立最小结构；SC-05 汇总候选时仍需保留该边界，Gate 2 通过前不得据此开发业务功能或部署生产数据库。

运行入口：`scripts/run-windows-validation.ps1`。脚本只使用仓库已准备的 PostgreSQL 18.6、pgvector 0.8.6 和 Python 3.13 离线环境，不访问外部网络。
