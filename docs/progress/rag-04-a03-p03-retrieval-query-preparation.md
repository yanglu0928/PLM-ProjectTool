# RAG-04-A03-P03：当前事实重验与 Retrieval Query 受控解密

日期：2026-10-04

状态：`PASS`

验证标记：`RAG_RETRIEVAL_QUERY_PREPARATION_PASS`

## Changed

新增 `RAGRetrievalQueryPreparationService` 和 PostgreSQL 当前事实仓储。执行先以专属 claim 的原请求 Actor 做无密钥预检，重验 User ENABLED、当前 Project/Membership/Department 角色和 License；随后在第二个短事务再次重验同一 Lease/Actor/角色，并有序锁定 Run、ACTIVE Project Index、精确 IndexSourceChunk、ACTIVE DocumentChunk、AVAILABLE EmbeddingRecord 和 QueryContent，所有事实一致后才读取专用 Query 密钥。

解密明文只能进入受权 callback 的 `bytearray`，严格 UTF-8 解码、NFKC/空白规范化并复算 `rag-query-v1` fingerprint。callback 只能执行同事务内的短数据库计算；返回、异常或第二次 License 失败都会归零缓冲。输出准备证明只含 Run/Job/Project/Actor/Index/Model、固定 filter、Top-K、query fingerprint 和当前授权快照 fingerprint，不记录明文、向量或 Secret。

执行链复核发现 A02 创建校验虽然文档声明只开放 PROJECT FTS，仍接受非空 GLOBAL Index。已按 CR-RAG-004 的既定首版边界修正：`fts.project.v1 + none.v1` 创建入口现在拒绝 GLOBAL Index，避免产生当前 Worker 必然失败的悬挂作业。

## Files

- `apps/backend/src/plm_assistant/modules/rag/application/create_retrieval.py`
- `apps/backend/src/plm_assistant/modules/rag/application/prepare_retrieval_query.py`
- `apps/backend/src/plm_assistant/modules/rag/infrastructure/retrieval_query_preparation_repository.py`
- `apps/backend/src/plm_assistant/modules/project/application/authorization.py`
- `apps/backend/tests/unit/test_rag_retrieval_create.py`
- `apps/backend/tests/unit/test_rag_retrieval_query_preparation.py`
- `apps/backend/tests/unit/test_project_authorization.py`
- `validation/rag-04-a03-p02-retrieval-claim/verify.py`
- `validation/rag-04-a03-p03-retrieval-query-preparation/`

## Migration / API / Compatibility

- Migration：无；复用 Schema0088 与现有 Project/Auth/Index/Embedding 表。
- API：无；冻结 `/api/v1` 不变。
- 权限：新增内部 `RAG_RETRIEVAL_EXECUTE`，与已批准创建角色一致，仅 ACTIVE Project 的 ProjectManager、ImplementationMember、CustomerManager 可继续原请求。
- 依赖/网络：无新增依赖、无 Provider I/O、无数据外发。
- 兼容修正：首个 `fts.project.v1` 明确拒绝 `global_index_ref`。未来 GLOBAL 合并须在 A04 的版本化策略和授权边界完成后另行开放；不改变已有合法 PROJECT 请求。
- 回滚：停止 Preparation/Worker 即可阻止新解密；已创建密文继续保留。不能恢复入口对 GLOBAL Index 的无实现接受，否则会重新制造不可执行作业。

## Tests

- 新增单元 5 项；相关定向 17 项 PASS，覆盖成功 callback/归零、禁用 Actor、License 失败、角色漂移、Target 漂移、query fingerprint 不匹配、callback 异常以及 PROJECT-only 创建修正。
- Windows 11 / PostgreSQL 18.6：真实 Session/Project 数据与合成 License/ACTIVE Index 下，当前 Lease/User/Membership/Index/Model/精确 Chunk/AVAILABLE Embedding/QueryContent 全链重验后仅一次密钥读取；解密明文与创建 query 一致并归零。成员暂停和 License 关闭均在读取密钥前拒绝。
- 后端全量：2478 项 PASS，3 项既有环境条件跳过。
- 开发 wheel 中 RAG 隔离回归：105 项 PASS，确认从 wheel 安装路径导入；SHA-256 `32fd62d069d23df52423d2a7e398ac8662c948740fbbb7da9fd120e6372eb9e3`。

## Result / Known Issues / Next

结果：`PASS`。本项提供受控 query 使用边界，不生成或持久化候选。合成 ACTIVE 只证明机制，不代表正式业务质量。过期 Reconciler、FTS 候选、候选/Context 原子发布、性能、Windows Server 2025、Debian 13、Gate 3、UAT 和发行包尚未通过。

下一项：`RAG-04-A03-P04`，在 Preparation callback 的同一受权事务内执行参数化 PROJECT FTS，应用固定 metadata AST、稳定排名和有界 Top-K，只返回不可变内存候选计划。
