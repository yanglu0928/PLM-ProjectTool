# RAG-04-A03-P04：参数化 PROJECT FTS 与有界候选计划

日期：2026-10-04

状态：`PASS`

验证标记：`RAG_PROJECT_FTS_CANDIDATE_PASS`

## Changed

新增数据库内 PROJECT FTS 候选 Planner/Repository。查询使用与 stored `simple` tsvector 一致的 `websearch_to_tsquery('simple', :query_text)`，正文仅作为 bind parameter；SQL 固定限制 Preparation 已锁定的 Project、Index、Model、精确 IndexSourceChunk、ACTIVE Chunk、AVAILABLE Embedding、AVAILABLE DocumentVersion 和 ACTIVE Document。

metadata 首版只映射 `document_category`、`source_type`、`document_version_ref` 三个固定字段；创建入口同步关闭尚无不歧义物理字段的 business/effective filter。排名用 `ts_rank_cd` 量化为整数微分值，并以 rank、source ordinal、ChunkId 稳定排序；候选池固定 `min(top_k*4,400)`。

输出为不可变内存计划，只含 Index/Model、Chunk/DocumentVersion/ParseResult、source type/locator、FTS 分数和授权快照 fingerprint，不含 query、正文或向量；本项不写 Candidate/Score/Context。

## Files

- `apps/backend/src/plm_assistant/modules/rag/application/create_retrieval.py`
- `apps/backend/src/plm_assistant/modules/rag/application/project_fts_candidates.py`
- `apps/backend/src/plm_assistant/modules/rag/infrastructure/project_fts_candidate_repository.py`
- `apps/backend/tests/unit/test_rag_project_fts_candidates.py`
- `apps/backend/tests/unit/test_rag_retrieval_create.py`
- `validation/rag-04-a02-p02-retrieval-create/verify.py`
- `validation/rag-04-a03-p02-retrieval-claim/verify.py`
- `validation/rag-04-a03-p04-project-fts-candidates/`

## Migration / API / Compatibility

- Migration/API/依赖：均无；冻结 `/api/v1` 不变，无 Provider I/O 或外发。
- 当前能力：仅 PROJECT FTS；GLOBAL/vector/exact query embedding/rerank 仍关闭。
- filter 兼容：已合法的三类固定 filter 保持；business/effective 输入在有正式字段/策略前拒绝，避免从任意 JSON 猜测。
- 回滚：停止 Planner 即停止候选计算；本项无持久历史。不能改为拼接 SQL、任意 JSONPath 或跨 Index fallback。

## Tests

- 新增单元 3 项；相关定向 13 项 PASS，覆盖安全候选、跨 Index/Model/授权漂移、ordinal 断裂与重复 Chunk 拒绝，以及未实现 filter 关闭。
- Windows 11 / PostgreSQL 18.6：参数化 `PLM` 查询从精确合成 ACTIVE Index 返回 1 条同项目候选，分数大于零、locator/来源正确；明文归零，Candidate/Score 表前后均为 0。
- 后端全量：2481 项 PASS，3 项既有环境条件跳过。
- 开发 wheel 中 RAG 隔离回归：108 项 PASS，确认从 wheel 安装路径导入；SHA-256 `df2f916abbd8d04c7ebe51d35eda55bb86b307ff5250470943f1e6e68ce7129f`。

## Result / Known Issues / Next

结果：`PASS`。`RAG-04-A03` 的 claim、当前事实/解密和 PROJECT FTS 内存候选链已完成，但 Job/Run 尚未终结，候选尚未持久化。合成 ACTIVE 不作业务质量证据。

下一项：`RAG-04-A04-P01`，核查 merge/vector/exact/rerank、外发授权、degraded/fallback 与当前仅 FTS 能力的最小兼容拆分；随后进入 A05 原子发布/终态 Owner。
