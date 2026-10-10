# RAG-04-A04-P02：FTS-only 合并与质量计划

日期：2026-10-04

状态：`PASS`

验证标记：`RAG_FTS_MERGE_PLAN_PASS`

## Changed

新增纯应用层 `FTSRetrievalMergePlanner`，对 A03 的 PROJECT FTS 候选按整数分数降序、原稳定 ordinal、ChunkId 排序并截取 Top-K。每条最终候选生成可复算的 `FTS` 与 `FINAL` ScorePart 计划；当前单通道权重固定 1.0，不做依赖候选集合的动态归一化。

`1..top_k-1` 条候选成功并标记 `CANDIDATE_SHORTFALL`，不标 degraded；零候选抛出 `RAG_NO_AUTHORIZED_CANDIDATES`，供 A05 原子失败终结且不创建空 Context。rerank/egress 固定 `NOT_APPLICABLE`，不触发网络或外发。

## Files

- `apps/backend/src/plm_assistant/modules/rag/application/fts_retrieval_merge.py`
- `apps/backend/tests/unit/test_rag_fts_retrieval_merge.py`

## Migration / API / Compatibility

- Migration、API、依赖、网络：均无。
- 当前仅实现 `fts.project.v1`；GLOBAL/vector/exact query embedding/rerank 保持关闭。
- 回滚：移除 Planner 即可；无持久历史。A05 将消费本计划并负责原子持久化。

## Tests

- 新增 4 项，相关定向 7 项 PASS：稳定 Top-K、ScorePart、shortfall 非 degraded、零候选失败、同分 ordinal 决胜。
- 后端全量：2485 项 PASS，3 项既有环境条件跳过。
- 开发 wheel 中 RAG 隔离回归：112 项 PASS，确认从 wheel 安装路径导入；SHA-256 `41cbb1c460c6874fe5d4c16ce3cee8a764f44ed7f72ad878cf23d4a403517942`。

## Result / Known Issues / Next

结果：`PASS`。A04 当前 FTS-only 策略合并完成；无真实 Provider I/O 或客户数据外发。扩展检索策略仍未开放，合成 ACTIVE 不作业务质量证据。

下一项：`RAG-04-A05-P01`，为 Candidate/Score/最小 Context 与 Job/Run 成功/失败、过期 generation 建立 Schema0089 原子提交边界。
