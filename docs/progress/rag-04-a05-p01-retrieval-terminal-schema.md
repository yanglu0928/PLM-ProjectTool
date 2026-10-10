# RAG-04-A05-P01：Retrieval 原子终态 Schema

日期：2026-10-04

状态：`PASS`

验证标记：`RAG_04_A05_P01_RETRIEVAL_TERMINAL_SCHEMA_PASS`

## Changed

新增 Schema0089，把 Retrieval 成功、已知失败和租约过期收敛为数据库提交期原子边界。成功提交必须同时具备同 generation 的 Job/Attempt/Lease 终态、固定 ACTIVE Index、1..Top-K 个 Candidate、每候选恰好两条 FTS/FINAL ScorePart，以及唯一 `project-documents.v1` ContextBundle 和按候选顺序完整覆盖的 ContextItem；候选不足标记 `CANDIDATE_SHORTFALL`。

正常失败与租约过期只允许固定错误码，并要求 Job/Attempt/Lease/Run 同步终结且 Candidate、ScorePart、Context 全部为零。仍处于 RUNNING 的 Run 不能提交任何结果行；终态和结果必须由同一数据库事务创建，防止半快照或旧 generation 补写。

## Files

- `apps/backend/src/plm_assistant/migrations/versions/20261004_0089_rag_retrieval_terminal.py`
- `apps/backend/src/plm_assistant/modules/rag/infrastructure/orm.py`
- `apps/backend/tests/unit/test_rag_retrieval_terminal_migration.py`
- `apps/backend/tests/unit/test_migration_contract.py`
- `validation/rag-04-a05-p01-retrieval-terminal-schema/README.md`
- `validation/rag-04-a05-p01-retrieval-terminal-schema/verify.py`

## Migration / API / Compatibility

- Migration：`20261004_0088 -> 20261004_0089`。无终态/结果历史时可降级；存在 Candidate、ScorePart、Context 或终态 Run 时拒绝降级并要求向前修复。
- API：无公开 API 变化；冻结 `/api/v1` 合同不变。
- 依赖、网络与数据外发：均无新增；验证只使用合成 ACTIVE Index 和合成文档事实。
- 回滚：停止 Retrieval Worker 可关闭新终态写入；已有不可变终态/结果历史保留，不能通过删除历史伪装回滚。

## Tests

- Windows 11 / PostgreSQL 18.6：Schema0088 已有库升级、ORM drift、空历史降级重升、完整成功、零候选失败、过期 generation 失败、Candidate 单独提交拒绝、缺 Context 成功拒绝、终态历史拒绝降级全部 PASS。
- 相关定向：32 项 PASS。
- 后端全量：2490 项 PASS，3 项既有环境条件跳过。
- 开发 wheel 中 RAG 隔离回归：117 项 PASS；确认从 wheel 安装路径导入。wheel SHA-256：`9c34322accd117ea004fd4d26eaa0ff5643f4541797de56babb6b28041a0bde1`。

## Result / Known Issues / Next

结果：`PASS`。Schema0089 已证明 Retrieval 结果集和 Job/Run 终态不能部分提交。迁移验证期间修正了两个实现偏差：不再假定 Attempt 与 Lease 的创建先后顺序，只要求均不晚于完成时刻；PL/pgSQL 局部变量改为无歧义命名并限定聚合列。

已知问题：本项只证明数据库边界；A05-P02 尚需实现发布 Owner、单次 Worker 组合与 AI `RAG_CONTEXT` 受权读取。合成 ACTIVE 不作正式业务质量证据；扩展检索策略、性能、Windows Server 2025、Debian 13、Gate 3、UAT 和发行包仍待后续任务关闭。

下一项：`RAG-04-A05-P02`，实现成功/失败/过期原子发布 Owner、一次性 Worker 编排和 AI `RAG_CONTEXT` 最小受权读取。
