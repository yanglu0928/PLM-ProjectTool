# RAG-04-A05-P02：Retrieval Worker 与 AI Context Owner

日期：2026-10-04

状态：`PASS`

验证标记：`RAG_04_A05_P02_RETRIEVAL_WORKER_CONTEXT_PASS`

## Changed

新增 Retrieval 成功、已知失败和租约过期发布 Owner，并以一次性 Worker 固定执行 `claim -> 当前事实/License 重验 -> 受控解密 -> 参数化 PROJECT FTS -> 稳定合并 -> 原子终态/Audit`。成功结果、Job/Attempt/Lease/Run 终态和 SYSTEM Audit 在同一事务提交；正常失败与过期 generation 同步关闭且结果集保持为零。终态提交不确定时只返回 `RECONCILIATION_PENDING`，不自动重放可能已执行的检索。

新增 AI `RAG_CONTEXT` 最小读取 Owner：只接受完整 Run/Bundle 身份，在当前 `AI_TASK_EXECUTE` Project 权限与 License 前后两次检查之间锁定精确 SUCCEEDED Run、Bundle、Item、Candidate、Chunk、当前 AVAILABLE DocumentVersion 和 ACTIVE Document；逐项复核 Project、顺序、locator、snippet fingerprint、token 与 bundle fingerprint 后才生成有界 JSON 文本。AI Invocation 准备链只允许登记过的 RAG context policy 调用 Owner，拒绝调用方自行注入正文。

实施中发现零分 FTS 行虽然存在但不能满足 Schema0089 的正分结果约束。已在内存合并边界过滤 `raw_score_micros <= 0`，全零集合统一收敛为 `RAG_NO_AUTHORIZED_CANDIDATES`，避免直到数据库提交期才出现内部错误。

## Files

- `apps/backend/src/plm_assistant/modules/rag/application/retrieval_terminal.py`
- `apps/backend/src/plm_assistant/modules/rag/application/retrieval_worker.py`
- `apps/backend/src/plm_assistant/modules/rag/application/retrieval_context.py`
- `apps/backend/src/plm_assistant/modules/rag/application/fts_retrieval_merge.py`
- `apps/backend/src/plm_assistant/modules/rag/infrastructure/retrieval_terminal_repository.py`
- `apps/backend/src/plm_assistant/modules/rag/infrastructure/retrieval_context_repository.py`
- `apps/backend/src/plm_assistant/modules/ai/infrastructure/rag_context_owner.py`
- `apps/backend/src/plm_assistant/modules/ai/application/execution_envelope.py`
- `apps/backend/src/plm_assistant/modules/ai/application/task_invocation_prepare.py`
- `apps/backend/tests/unit/test_rag_retrieval_worker.py`
- `apps/backend/tests/unit/test_rag_context_read.py`
- `apps/backend/tests/unit/test_rag_fts_retrieval_merge.py`
- `apps/backend/tests/unit/test_ai_execution_envelope.py`
- `validation/rag-04-a05-p02-retrieval-worker-context/README.md`
- `validation/rag-04-a05-p02-retrieval-worker-context/verify.py`

## Migration / API / Compatibility

- Migration：无；继续使用 Schema0089。
- API：无公开 API 变化；冻结 `/api/v1` 合同不变。
- 依赖、网络与数据外发：均无新增；首个 `fts.project.v1 + none.v1` 策略只访问本地 PostgreSQL，验证仅使用隔离合成事实。
- 兼容：现有 `NONE` AI context policy 保持原行为；RAG policy 必须显式登记且由 Owner 提供非空最小文本。零分 FTS 候选由提交期错误提前收敛为受控零候选失败。
- 回滚：可停止 Retrieval Worker 并撤除 RAG context policy/Owner 组合；已经提交的不可变 Run、结果和 Audit 历史保留，未知终态先对账，不得重放或删除历史。

## Tests

- Windows 11 / PostgreSQL 18.6：真实 Schema0089 事务完成成功检索、Audit、Context 当前授权读取、撤权后关闭、零候选已知失败、租约过期原子对账及失败结果集为零，标记 `RAG_04_A05_P02_RETRIEVAL_WORKER_CONTEXT_PASS`。
- RAG 单元：125 项 PASS；AI Context/Envelope 定向：8 项 PASS。
- 后端全量：2498 项 PASS，3 项既有环境条件跳过。
- 开发 wheel 隔离导入：RAG 125 项、AI Context/Envelope 8 项 PASS。wheel SHA-256：`71116eb41d492a683bc85372d01dbc9784366eb298f700c729b9adc4772cbbdd`。

## Result / Known Issues / Next

结果：`PASS`。首个零外发 PROJECT FTS 策略已经具备从创建后的专属 claim 到不可分割结果发布，以及到 AI Invocation 准备阶段最小读取的内部闭环。

已知问题：本项没有挂载公开 Retrieval HTTP、生产 Worker 循环或部署策略；AI Task 的公开请求仍需 A06 把精确 Retrieval/Context 身份接入冻结 API 与组合根。合成 ACTIVE 不作正式业务质量证据；扩展 vector/GLOBAL/rerank 策略、性能、Windows Server 2025、Debian 13、Gate 3、UAT 和发行包仍待后续任务关闭。

下一项：`RAG-04-A06-P01`，执行冻结 Create/Get/Result/Context/Cancel HTTP 与现有 Owner/Job 合同的编码前核查，并拆分安全接线与 Windows 11/PostgreSQL 18 验收。
