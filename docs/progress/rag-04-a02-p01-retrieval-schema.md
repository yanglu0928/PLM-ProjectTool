# RAG-04-A02-P01：RetrievalRun / Candidate / Context Schema0088

日期：2026-10-04

状态：`PASS`

验证标记：`RAG_RETRIEVAL_SCHEMA_PASS`

## Changed

Schema0088/ORM 新增 RetrievalRun、专用加密 QueryContent、Candidate、ScorePart、ContextBundle 与 ContextItem 六张表。Run 只持有 query/filter SHA-256 和安全引用；Job payload 固定只含 `retrieval_run_id`。候选绑定当前 ACTIVE Index、精确 Chunk 来源和 AVAILABLE Embedding，分数使用整数微分值，Context 只保存引用、locator、截取范围、token 与指纹。

数据库提交期要求 Run 同事务具有 QueryContent。Run 的状态更新和 Context 写入在后续 Owner 落地前关闭；Candidate/Score 即使直接写也必须通过 Project/Index/Chunk/Embedding/Run 绑定守卫。所有表禁止 UPDATE/DELETE/TRUNCATE；有历史拒绝物理降级。

## Files

- `apps/backend/src/plm_assistant/migrations/versions/20261004_0088_rag_retrieval_foundation.py`
- `apps/backend/src/plm_assistant/modules/rag/infrastructure/orm.py`
- `apps/backend/tests/unit/test_rag_retrieval_foundation_migration.py`
- `validation/rag-04-a02-p01-retrieval-schema/`
- `docs/database-schema/rag-retrieval-foundation-0088-increment.md`

## Migration / API

- Migration：`20261004_0088`，down revision `20261004_0087`。
- API：无；冻结 Create/Get/Result/Context/Cancel 尚未挂载。
- 依赖/网络：无新增依赖，无真实 Provider I/O，无客户数据外发。

## Tests

- Windows 11 / PostgreSQL 18.6：空库与已有 User+Project 升级、drift、空历史降级/重升、有历史拒降 PASS。
- 合成 ACTIVE 组合：Run+密文 query、Candidate/Score 正向；缺 QueryContent、Run 状态直改、Context 提前写入拒绝 PASS。合成 ACTIVE 不作为正式业务质量。
- Migration/ORM 定向 12 项 PASS；RAG wheel 隔离 86 项 PASS。
- 后端全量：2458 项 PASS，3 项既有环境条件跳过。
- wheel SHA-256：`4fb5d1c4f465be331807cc1dcbcbddd8746216fe641d881bb22224e2c643b4fc`。

## Result / Known Issues / Next

结果：`PASS`。Schema 事实与关闭边界已具备，但创建 Owner、专用 QueryCipher、Session/CSRF/Membership/License、Audit/幂等和真实 Worker 均未实现，不能对外创建 RetrievalRun。正式 ACTIVE、内容密钥、业务质量、性能、Windows Server 2025、Debian 13、Gate 3、UAT 和发行包未通过。

下一项：`RAG-04-A02-P02` 受权异步创建 Owner，以同一事务创建密文 QueryContent、Run、Job、Audit 和幂等回执，并重验当前 Project/Index/License。
