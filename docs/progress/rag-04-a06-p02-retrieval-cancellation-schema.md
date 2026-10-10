# RAG-04-A06-P02：Retrieval 原子取消 Schema0090

日期：2026-10-04

状态：`PASS`

验证标记：`RAG_04_A06_P02_RETRIEVAL_CANCELLATION_SCHEMA_PASS`

## Changed

新增 Schema0090，将冻结模型已有的 RetrievalRun `CANCELLED` 纳入提交期边界。PENDING Job 只允许经过取消请求后以 v2 和零 Lease/Attempt 同步终结 Run；RUNNING Job 只允许以 v3、单次 generation、RELEASED/EXPIRED Lease、`JOB_CANCELLED` Attempt 和同完成时点同步终结。两种形态都要求取消申请事实完整且 Candidate/Score/Context 全部为零。

真实数据库负例发现 Schema0089 validator 在 Run 仍为 RUNNING 时直接返回，未阻止 Job 单独进入终态。Schema0090 同步修复该偏差：Job 的 SUCCEEDED/FAILED/CANCELLED 只要 Run 尚未同步终结，提交即失败；既有成功/失败完整事务仍保持兼容。

## Files

- `apps/backend/src/plm_assistant/migrations/versions/20261004_0090_rag_retrieval_cancellation.py`
- `apps/backend/src/plm_assistant/modules/rag/infrastructure/orm.py`
- `apps/backend/tests/unit/test_rag_retrieval_cancellation_migration.py`
- `apps/backend/tests/unit/test_migration_contract.py`
- `docs/database-schema/rag-retrieval-cancellation-0090-increment.md`
- `validation/rag-04-a06-p02-retrieval-cancellation-schema/README.md`
- `validation/rag-04-a06-p02-retrieval-cancellation-schema/verify.py`

## Migration / API / Compatibility

- Migration：`20261004_0089 -> 20261004_0090`；无取消历史可降，有取消请求/终态历史拒降并向前修复。
- API：无公开 API 行为变化；本项只提供后续冻结 Cancel HTTP 所需数据库边界。
- 依赖、网络与外发：无新增；验证仅使用隔离合成 Project/Index/Run。
- 回滚：先停止新取消和 Retrieval Worker；无取消历史可降0090，有历史保留并前向修复。

## Tests

- Windows 11 / PostgreSQL 18.6：0089已有数据升级、ORM drift、空取消历史降级重升、PENDING直接取消、RUNNING协作取消、Job-only半终态和取消带结果回滚、取消历史拒降全部 PASS。
- 在0090 head重跑0089完整成功、正常失败、租约过期、半Candidate/缺Context回滚及终态历史保护，全部 PASS。
- Migration/Retrieval定向：14 项 PASS。
- 后端全量：2503 项 PASS，3 项既有环境条件跳过。
- 开发 wheel 隔离导入：RAG 130 项、Migration Contract 4 项 PASS。wheel SHA-256：`8fa75bb94f43fea0cb6be8486725846816e83c4e4aa410bd1176ddb23851fb3d`。

## Result / Known Issues / Next

结果：`PASS`。数据库已能表达并强制冻结取消语义，同时关闭旧 terminal validator 的 Job-only 终态漏洞。

已知问题：本项尚无取消 Application Owner/Reconciler/HTTP；P03先实现当前受权只读，P05再接取消。正式 ACTIVE、业务质量、性能、Windows Server 2025、Debian 13、Gate 3、UAT 和发行包仍待。

下一项：`RAG-04-A06-P03`，实现当前受权的 Run/Result/Context 最小只读 Owner。
