# RAG-04-A06-P04：Retrieval Create/Get/Result/Context HTTP 合同

日期：2026-10-04

状态：`PASS`

验证标记：`RAG_04_A06_P04_RETRIEVAL_HTTP_PASS`

## Changed

新增默认关闭、仅显式依赖注入后挂载的 Retrieval HTTP Router，落实冻结的四个 Operation：

- `POST /api/v1/projects/{project_id}/retrieval-runs`
- `GET /api/v1/projects/{project_id}/retrieval-runs/{retrieval_run_id}`
- `GET /api/v1/projects/{project_id}/retrieval-runs/{retrieval_run_id}/result`
- `GET /api/v1/projects/{project_id}/retrieval-runs/{retrieval_run_id}/context`

Create 严格接受七字段请求，ProjectId 只取路径；当前首版只允许 PROJECT、`fts.project.v1`、`none.v1`、`top_k=1..100`，拒绝 GLOBAL、vector、rerank、额外字段、重复 JSON key 和 query string。写请求依次校验 Origin、Session、CSRF、幂等键，再委托既有创建 Owner，并只返回 Run/Job 引用。

三类读取只接受可信 Host 和 Session，委托当前受权读取 Owner；Run 不返回 query、filter、密文、向量或 fingerprint，Result/Context 只返回已收窄的来源、整数分数与最小 snippet。Router 对 Owner 返回值再做 ProjectId/RunId 绑定与 DTO 自校验，异常投影失败关闭。所有响应 `no-store`，读取响应增加 `nosniff`，Run 返回强格式版本 ETag。

## Files

- `apps/backend/src/plm_assistant/modules/rag/api/__init__.py`
- `apps/backend/src/plm_assistant/modules/rag/api/retrieval_runs.py`
- `apps/backend/src/plm_assistant/entrypoints/api.py`
- `apps/backend/tests/contract/test_rag_retrieval_api.py`

## Compatibility / Upgrade / Rollback

- 冻结 URL、Operation 语义和安全控制保持；A06-P03 已登记的 query fingerprint 最小化收紧继续生效。
- 无 Migration、依赖、生产组合、网络或数据外发；默认 `create_app()` 仍返回 404，P06 完成生产依赖与密钥组合前不能开放真实流量。
- 可撤除可选 Router 参数和 Router 文件回滚；数据库历史及内部 Owner 不变。
- 本项没有重复 PostgreSQL 真实性验证：创建与三类读取 Owner 已分别在 A02-P02/P03 完成 Win11/PG18.6 实证，本项是隔离 HTTP 合同；真实 HTTP→Worker→Result/Context/Cancel 由 P08 验收。

## Tests

- HTTP 合同 5 项 PASS：默认关闭、严格 Create、四类安全投影、错误映射、跨 Project/Run 返回绑定、非法 query/Origin/CSRF/幂等输入。
- RAG 单元 135 项 PASS；后端全量 2513 项 PASS，3 项既有环境条件跳过。
- 开发 wheel 隔离导入：明确证明模块来自解包目录，RAG 135 项、HTTP 合同 5 项、Migration Contract 4 项 PASS。wheel SHA-256：`e70068a741ad18a0d5eda3796a813ad021f7da1e33b95b0149056567d5beca96`。
- 首次 wheel 隔离命令使用了不存在的 PowerShell `Select-Object -Single` 参数，导致未解包且该轮结果作废；改用单文件计数、新目录、打印导入路径后完整重跑通过，未修改产品实现。

## Result / Known Issues / Next

结果：`PASS`。四个冻结 HTTP Operation 已形成严格、默认关闭且可组合的契约面；没有把尚未完成的生产装配描述为可用。

已知问题：Cancel Owner/双路径接线、生产 API/第四 Worker 组合、前端、真实浏览器闭环、正式质量/性能、Windows Server 2025、Gate 3、UAT 和发行包仍待；Debian 13 按用户指令跳过。

下一项：`RAG-04-A06-P05`，实现 Retrieval Cancel Owner、专属取消 Reconciler、冻结别名 Router与通用 Job cancel registry 同 Owner 接线。
