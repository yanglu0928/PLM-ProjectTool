# CR-AI-022：AI Task 与 Job 初始状态投影修正

日期：2026-10-04；状态：`IMPLEMENTED_AND_WINDOWS11_BROWSER_VERIFIED`；WBS：`AI-05-A07`。关联冻结 API-03 Task/Job 读取合同；原 Gate 2 冻结提交 `64cdf09`、现有 Schema 与公开 DTO 不改。

## 差异与原因

AI Task 创建的既定合法初始状态是 `Task=QUEUED`、`Job=PENDING`。既有 Job Owner 读取仓储却错误要求 `task_state == job.state`，导致真实创建成功后从 AI Task 详情跳转到运行任务详情得到 `SYSTEM_UNAVAILABLE/503`。这是内部跨聚合状态映射遗漏，不是冻结 API 或数据事实需要改变。

修正为显式允许的状态对：`QUEUED/PENDING`、`RUNNING/RUNNING` 以及同名的 `SUCCEEDED`、`FAILED`、`CANCEL_REQUESTED`、`CANCELLED`。未知组合、`QUEUED/RUNNING` 等不一致状态继续失败关闭；`retryable` 仍只由匹配的终态 Task 产生。

## 风险、兼容、迁移与回滚

- 风险：过宽状态映射会掩盖竞态或损坏；因此采用封闭集合，不使用一般性“非终态均允许”。
- 兼容：公开 URL、响应 DTO、权限、ETag、Task/Job 写状态机均不变，只恢复原本应可读取的合法初始 Job。
- 迁移：无 ORM/Alembic、数据回填或依赖变化。
- 回滚：可撤内部映射与回归，但会恢复新建 AI Task 的 Job 详情 503，故不建议；历史 Task/Job 不改写。

## 验证结果

新增 3 项仓储回归，覆盖合法 `QUEUED/PENDING`、非法错配失败关闭和匹配 `FAILED/FAILED` 的重试投影；相关 9 项通过。后端全量 2349 项通过、3 项既有条件跳过；开发 wheel 823 项，SHA-256 `b0c2325b1a3b67806ee9da1956ce7761fc8937363bb08b5a3785de2728953af7`。

Windows 11 build 26200、Edge 154、PostgreSQL 18.6 的最终全新隔离链完成创建、Task详情、零Invocation、Job详情、浏览器返回与工作台列表回显；浏览器实际观察四类读取均为 200，数据库保持1个 `QUEUED` Task、1个 `PENDING` Job、0 Invocation，临时资源全部清理。无真实 Provider I/O、客户数据或 Secret 外发。
