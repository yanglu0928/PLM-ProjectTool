# AI-04-A06-P08-P05-P01 显式 Retry generation Schema

日期：2026-10-03；状态：`RETRY_GENERATION_SCHEMA_PASS`。

Changed/Files：新增 Schema0075、`AITaskRetryGenerationRow`、迁移/元数据合同测试、Windows 11/PostgreSQL 18.6 验证脚本及数据模型/决策/版本记录。Migration：0074→0075 仅追加 `ai_task_retry_generations`，旧 Task 不回填；无血缘可降级，有血缘拒绝降级。API/Dependencies：无变化，本项不开放 Retry Owner。

数据库强制只能由可重试 `FAILED`或安全取消 `CANCELLED` 终态派生新 `QUEUED/PENDING` Task/Job，新旧 Task 的 Prompt/Policy/Parameters/Content Plan、有序 Input refs 和 Egress 快照不得漂移；根/代际、Job ETag 版本、实际请求人与 USER Audit 必须一致。远程结果未知的 `FAILED/retryable=false` 不能通过。

Tests：定向 Schema/ORM 6项通过；Win11/PG18.6 完成空库和历史库升/降/重升、Alembic drift、合法血缘、错根/错版本/更新/截断/有历史降级负例；后端全量 2269 项通过/3项既有条件跳过；开发 wheel 797项，SHA-256 `46467de977e9898296dcdb02d53dab7a26178e6cb52cad803b5e0eba54a946d0`。首次全量命令误用不完整依赖目录导致导入错误，同时发现并修正迁移头断言；改用项目完整 Python 3.13 验证环境后从头通过。

Known Issues/Next：P02 尚需实现当前 Session/CSRF/License/项目权限、当前 Egress 有效性、源状态和幂等收据重验，再在单一写事务中创建新 Task/Job/Outbox/Input/Snapshot/Audit/Lineage。无真实 Provider 网络或客户数据外发。
