# CR-PAR-002：Parser 项目取消的首次响应版本证据

日期：2026-09-30；Phase 2 / PAR-01-A05-P01-P04-P03-P01；状态：持续授权下实施中。原 Gate 2 冻结提交 `64cdf09` 不改，Gate 3 未通过。

## 来源、差异与选择

冻结 API-03 已规定项目 Job Cancel 支持创建者或 Project Manager、`If-Match`、幂等、原结果重放。现有 Document Parse Job 有内部 Worker 协作取消，却没有用户取消 Owner。通用幂等收据只存 Audit 事件引用；事件保存首次状态但不保存 `lock_version`。Worker 后续确认会推进版本，从当前 Job 反推首次响应属于错误事实。Audit Export 的 `aud_export_cancel_versions` 是其专属来源，不能混用。

选择新增 Jobs 自有的 `job_parse_cancel_versions`：仅保存 USER 取消 Audit 事件 ID 与当时非负 Job 版本；事件提供状态、行为人、项目及 Job 来源。数据库插入触发器限制真实 PROJECT/DOCUMENT_PARSE Job 的首次取消或终态检查事件，UPDATE/DELETE/TRUNCATE 一律拒绝。不改 `/api/v1`、七字段 License、Job/Document 原表或旧迁移，不新增外部依赖。后续 Owner 在同一 UOW 内依据实际上传/版本/Outbox/Audit 来源、当前权限与 Lease 写取消、Audit、版本和幂等收据；不能把 dispatch hint 当权限。

## 风险、升级与回滚

潜在风险为来源绑定错误、首响应版本漂移和既有数据库升级。先验证空库及有数据升级、来源约束和并发/故障回滚。正式升级前需备份并停止 API/Worker 写入；无新快照时可降级，已有快照的 downgrade 必须拒绝以防历史丢失。回退应用可关闭 Parser 取消 Owner 并保留新增表，不改写旧历史；生产恢复与三平台发行另验。取消理由不可出现在版本表或日志，客户资料不外发。

## 验收边界

P01 只关闭 ORM/Migration 与数据库来源、历史保留验证；P02 再关闭当前授权 Owner、幂等首响应、HTTP 接线及真实文件/PG 矩阵；P03 再处理过期取消/崩溃恢复。任何一个子项均不提前关闭 Gate 3、UAT 或可使用包。

2026-09-30 P01 结果：`0050` 与 ORM、空库和已有 Job 数据升降级、来源及不可变约束、含快照拒绝降级在 Windows 11 隔离 PostgreSQL 18 通过；Python 3.13 后端全量 1632 项（3 项环境跳过）及开发 wheel 通过。仅 Schema/ORM 基础，Owner 未挂载；正式生产升级、跨平台及 Gate 仍未验证。

2026-09-30 P02 结果：当前授权 Parser Owner 已接入现有 Job Cancel 路由及 Windows 显式写组合；真实合成上传/PG18/HTTP 创建者或 PM、跨项目/撤权/License/CSRF 拒绝、PENDING/RETRY_WAIT/RUNNING、并发幂等原 ETag、末端故障回滚及只读模式关闭均 PASS；Python3.13 后端 1635 项（3 跳过）与 wheel PASS。正式信任源/三平台、P03 过期恢复和 Gate3 未通过；CR 保留追踪。
