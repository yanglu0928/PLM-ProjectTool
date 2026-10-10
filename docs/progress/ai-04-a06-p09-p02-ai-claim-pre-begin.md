# AI-04-A06-P09-P02 Owner 专用 AI Task claim 与 pre-Begin 失败收敛

日期：2026-10-03；状态：`AI_TASK_CLAIM_PRE_BEGIN_PASS`；依据 CR-AI-019、DEC-764，无公开 API、Schema 或第三方依赖变化。

新增 Jobs-owned `claim_next_ai_task`，只允许业务 Worker 领取 `ai/AI_TASK_EXECUTE`，不会跨 Owner 抢占 Audit、Document 或 Provider Probe。新增 pre-Begin 失败 Owner：当 prepare 在 Invocation 创建前失败时，在同一个短事务内关闭 Job/Attempt/Lease 和 Task，追加 SYSTEM Project Audit，并强制 Job 终态 `FAILED`，不进入通用自动 `RETRY_WAIT`。Task 的 `retryable` 仅保留为用户显式新 generation 的资格事实。

验证：新单元 4 项，相关定向 29 项；Windows 11/PostgreSQL 18.6 一次性数据库证明 Owner 隔离、Job/Attempt/Lease/Task/Audit 原子关闭、零 Invocation，注入 Audit 故障后全链回滚并可使用原 Lease 安全重试收敛。首次全量运行误用旧 PoC venv，因该环境缺后加的 `pydantic-settings` 产生导入错误；切换到完整依赖运行器后全量重跑，后端 2280 项通过、3 项既有条件跳过。最终 wheel 803 项，SHA-256 `5515e05e104437824aa2d5131a0398347afb015624de33a772c4cc39eb738b1f`。无真实 Secret、Provider 网络或客户数据外发。

兼容/回滚：仅追加内部领取与失败发布能力，既有通用和 Parse claim 语义不变。回滚可停止业务 AI 消费并撤销新组合；已提交的终态和 Audit 必须保留。

Next：`AI-04-A06-P09-P03` 业务 AI one-shot Worker。
