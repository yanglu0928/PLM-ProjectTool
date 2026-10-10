# Schema0090：RAG Retrieval 原子取消增量

日期：2026-10-04

Revision：`20261004_0090`；前序：`20261004_0089`

## 目的

落实冻结 DM-04/API-03 已定义的 Retrieval `CANCELLED`，并确保通用 Job 的 PENDING 直接取消或 RUNNING 协作取消都不能与 RetrievalRun 分裂。该增量同时修复 Schema0089 terminal validator 在 Run 仍为 RUNNING 时过早返回、未拒绝 Job 单独进入 SUCCEEDED/FAILED 的提交期缺口。

## 状态与原子形状

- Run 只允许 `RUNNING/v0 -> CANCELLED/v1`，身份、Project、Actor、Index、Policy、Job 和 Trace 不可改；取消终态固定 `rerank/egress=NOT_APPLICABLE`、空 quality、`error_code=NULL`、有完成时点、零结果。
- PENDING 直接取消：Job 经过 CANCEL_REQUESTED 后为 `CANCELLED/v2`，attempt/fencing 均为0，不存在 Lease/Attempt，Job/Run完成时点一致。
- RUNNING 协作取消：Job 为 `CANCELLED/v3`，attempt/fencing 均为1；Lease 为 RELEASED 或到期后 EXPIRED，Attempt 以 `JOB_CANCELLED` 同时完成，Job/Run完成时点一致，取消请求不得早于 Lease 获取。
- Job `CANCEL_REQUESTED` 时 Run 暂保持 RUNNING，等待专属 Reconciler；Job 任一终态与 Run RUNNING 的半提交被 deferred validator 拒绝。
- CANCELLED 下 Candidate、ScorePart、ContextBundle、ContextItem 必须全部为零。

## 升级、降级与回滚

升级替换 Retrieval lifecycle check、Run guard 和六个 deferred aggregate triggers；不改表列、不迁移现有数据。升级前应备份并在维护窗口执行 `0089 -> 0090`，随后运行 Alembic drift 检查。

无取消请求/取消终态历史时可降回0089；存在任一 RAG Retrieval CANCEL_REQUESTED/CANCELLED 或取消申请人事实时拒绝降级，必须保留历史并向前修复。应用回滚可先停止新取消/Worker并撤 Router；不得通过删除 Job/Run/Audit 历史规避降级保护。
