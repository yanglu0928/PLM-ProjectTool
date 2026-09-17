# POC-02 验收矩阵

|ID|验收项|Windows 11|Windows Server 2025|Debian 13|证据要求|
|---|---|---|---|---|---|
|P02-A01|环境与权限采集|PASS|PASS|DEFERRED_BY_USER|脱敏环境 JSON|
|P02-A02|PostgreSQL 18 官方制品可访问|PASS|PASS|DEFERRED_BY_USER|URL、版本、HTTP 状态、大小|
|P02-A03|pgvector PostgreSQL 18 支持证据|PASS|PASS|DEFERRED_BY_USER|官方文档、tag、commit|
|P02-A04|离线制品清单与 Hash|PASS|PASS|DEFERRED_BY_USER|manifest + SHA-256|
|P02-A05|完全离线安装/解压|DEFERRED_BY_USER|PASS|DEFERRED_BY_USER|安装日志、网络隔离说明|
|P02-A06|`initdb` 与启动/停止|PASS|PASS|DEFERRED_BY_USER|版本、端口、状态日志|
|P02-A07|`CREATE EXTENSION vector`|PASS|PASS|DEFERRED_BY_USER|扩展版本、SQL 输出|
|P02-A08|基础向量增删改查|PASS|PASS|DEFERRED_BY_USER|SQL 结果|
|P02-A09|SQLAlchemy 2.x / psycopg 连接|PASS|PASS|DEFERRED_BY_USER|自动化验证结果|
|P02-A10|Alembic 空库 up/down|PASS|PASS|DEFERRED_BY_USER|迁移日志|
|P02-A11|Alembic 有数据升级|PASS|PASS|DEFERRED_BY_USER|数据前后校验|
|P02-A12|10 万条向量导入|PASS|PASS|DEFERRED_BY_USER|条数、耗时、数据 Hash|
|P02-A13|HNSW 建索引与检索|PASS|PASS|DEFERRED_BY_USER|DDL、Explain、延迟、Recall|
|P02-A14|备份与恢复|PASS|PASS|DEFERRED_BY_USER|dump/restore 日志与校验|
|P02-A15|重启后健康检查|PASS|PASS|DEFERRED_BY_USER|进程、连接、数据校验|

## 判定规则

- `PASS`：已执行且证据满足要求。
- `NOT_RUN`：尚未执行，不得视为失败或通过。
- `BLOCKED_TOOLCHAIN`：已确认缺少执行所需工具链。
- `FAIL`：已执行且验收标准未满足，必须补充完整失败分析。
- `DEFERRED_BY_USER`：仅可在用户明确批准并登记例外后使用。

POC-02 只有全部当前必需项通过，或未执行项取得独立用户例外后，才能收口。
