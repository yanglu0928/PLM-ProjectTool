# RAG-04-A03-P02：Retrieval 专属单次 Claim 与通用队列隔离

日期：2026-10-04

状态：`PASS`

验证标记：`RAG_RETRIEVAL_CLAIM_PASS`

## Changed

新增 Jobs Owner 管理的 `RAGRetrievalClaim`、应用服务和 PostgreSQL 仓储。专属 claim 只接受 `rag/RAG_RETRIEVAL`、PROJECT scope、唯一 `retrieval_run_id` payload、Run ID 幂等键、原始 Actor/Trace，以及固定 `max_attempts=attempt_no=fencing_token=1`；`check_current` 在后续执行检查点重验相同当前租约。

通用 Job claim 同时在 ready 和 expired 路径排除 Retrieval；Parser、AI Task 和 RAG Index Build 专属入口因 Owner filter 不能接管 Retrieval。Retrieval 专属入口也不重领过期 generation，避免在 Run 完成/失败 Owner 尚未开放时只修改 Job/Lease/Attempt。

## Files

- `apps/backend/src/plm_assistant/modules/jobs/application/lease.py`
- `apps/backend/src/plm_assistant/modules/jobs/application/rag_retrieval_claim.py`
- `apps/backend/src/plm_assistant/modules/jobs/infrastructure/lease_repository.py`
- `apps/backend/src/plm_assistant/modules/jobs/infrastructure/rag_retrieval_claim_repository.py`
- `apps/backend/tests/unit/test_job_lease.py`
- `apps/backend/tests/unit/test_rag_retrieval_claim.py`
- `apps/backend/tests/unit/test_rag_retrieval_claim_repository.py`
- `validation/rag-04-a03-p02-retrieval-claim/`

## Migration / API / Compatibility

- Migration：无；复用现有 Job/Lease/Attempt 与 Schema0088 RetrievalRun。
- API：无；冻结 `/api/v1` 不变。
- 依赖：无新增。
- 行为兼容：仅收紧内部 Job 路由。通用 Worker 不再看见待执行或过期 Retrieval；RAG Build/AI/Parser 行为保持不变。
- 回滚：可停止专属 Retrieval Worker，但不能把已认领或过期作业交回通用 claim。其历史必须由后续专属 Reconciler 同时收敛 Job、Run 与 Audit。

## Tests

- 定向单元：16 项 PASS；覆盖通用服务输入、Claim DTO、当前 generation、仓储 payload/幂等/attempt/fencing/scope 漂移拒绝及既有 RAG Build 回归。
- Windows 11 / PostgreSQL 18.6：复用合成 ACTIVE Index 和受权 Retrieval 创建，证明通用、Parser、AI Task、RAG Build 均不能抢占；专属 Worker 精确认领；第二 Worker不能重复领取；租约过期后通用和专属入口均不重领，Job `RUNNING/1/1/1`、Lease generation 和 Run `RUNNING/v0` 未分裂。
- 后端全量：2473 项 PASS，3 项既有环境条件跳过。
- 开发 wheel 中 RAG 隔离回归：100 项 PASS；确认从 wheel 安装路径导入；SHA-256 `5d463c4c635d33a2607a9cd0985a7969d633ba9569ef49c719c94f6078977013`。

## Result / Known Issues / Next

结果：`PASS`。本项只证明认领和过期隔离，不解密 query、不访问候选正文、不执行 Provider I/O、不修改 RetrievalRun 状态。合成 ACTIVE 只证明机制，不作为业务质量、Gate 3 或 UAT 证据。

下一项：`RAG-04-A03-P03`，在当前 claim 下重验 License、原请求 Actor/Membership、Run/Index/Model/来源与 QueryContent 绑定，然后受控解密、复核 query fingerprint 并归零明文缓冲。
