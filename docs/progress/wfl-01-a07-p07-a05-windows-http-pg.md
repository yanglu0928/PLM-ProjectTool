# WFL-01-A07-P07-A05：Windows 生产组合与真实 HTTP/PostgreSQL 闭环

日期：2026-10-06。结论：`WFL_01_A07_P07_A05_WINDOWS_HTTP_PG_PASS`。

## 完成范围

- 新增 Windows Checklist 生产组合根，装配真实 Session/CSRF、License、ProjectManager
  授权、Handover 当前事实 Owner、Document/Parse/Evidence/Capability/AI/Review/Trace、
  不可变追加、历史重放、幂等和 Audit；只在 `--platform-write` 能力中挂载，普通 Platform
  与默认应用继续关闭。
- 使用真实 Approved Handover/Review、三条 PROJECT Evidence、固定 Document 物理字节、
  CURRENT_APPROVED Capability、SUCCEEDED GAP_ANALYSIS 和 VERIFIED Action，通过冻结 HTTP
  记录 `HANDOVER_ISSUES=PASS`。
- 同一 Idempotency-Key 返回原不可变 Record，数据库仅有一条 Checklist Record、一条成功
  Audit 和一条完成 receipt；响应的记录版本为 v2，当前 ETag 亦为 v2。
- 错误 Origin 返回 403，未注入 Router 返回 404；原 HND-03 Evidence 失效和文件篡改拒绝
  仍通过。

## 偏差与兼容

首次真实写链暴露普通 Document 下载另开授权事务造成 Session 自锁。按
[CR-WFL-007](../changes/CR-WFL-007-checklist-document-proof-transaction.md) 新增调用方事务内
Document/Parse 证明路径；不降低授权或物理字节校验。无 Schema/Migration、冻结请求、
角色、依赖、Secret 或外发变化。

真实 Trace Target Owner 仍未注册，因此 CLOSED Action 资格失败关闭；本项只以 VERIFIED
Action 完成正例，不外推为 Survey/Requirement Resolution 已支持。Debian 13 按用户指令
不实机验证，Server 2025 当前程序链仍是发行矩阵开放项。

## 验证证据

- 事务/Document/Parse、Checklist HTTP 与生产入口相关定向 58 项通过。
- Windows 11/PostgreSQL 18.6 一次性数据库迁移与 Alembic check、真实 HTTP 两次重放、
  PostgreSQL Record/Audit/receipt、Handover 当前事实锁与漂移拒绝通过；临时库/文件清理。
- 后端全量 2754 项运行、3 项按既有条件跳过、0 失败。
- 开发 wheel SHA-256：
  `5dcda0d86389bfcb71f4b7a783d67537720940d7393b4b91899a403b44d0ae29`；不是可发行程序包。

下一项：`WFL-01-A07-P07-A06` 前端 Checklist 记录安全客户端与 Workflow 页面接线。
