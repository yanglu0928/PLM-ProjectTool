# AI-04-A03-P05：AITask 执行 Job 绑定

- 日期：2026-10-02
- 结果：PASS（Windows 11 / PostgreSQL 18.6 隔离验证）
- 依据：CR-AI-011、DEC-702、冻结 `AI_TASK_CREATE`

## 变更

Schema0066 为 `ai_tasks.job_ref` 建立非空值唯一索引，并将迁移后新 Task 插入纳入数据库守卫：必须先存在唯一 `ai/AI_TASK_EXECUTE` Job，Job 的 Scope、Project、Actor、Trace 和 `payload_refs.ai_task_id` 必须与 Task 精确一致。`job_ref` 加入 Task 不可变身份，防止后续换绑。

0063～0065 已有 NULL 行保持原样，不猜测补值；此类历史不能用于后续执行。在只有旧 NULL 历史时可降回0065，一旦存在完整绑定则拒绝降级。

## 验证

- PostgreSQL 18.6：空库 up/down/re-up，旧0065 NULL 历史升级/降级/重升，Alembic drift=0。
- 负例：新 Task 缺 Job、Job 所有者错误、Job 复用、Task 换绑均被拒绝；完整新历史拒绝 down。
- 首轮夹具因 psycopg 未显式使用 JSONB 适配器而在写入 Job 前停止；改用 `Jsonb` 后从空库完整重跑 PASS。
- 后端全量：2106 项运行，3 项按既有环境条件跳过，无失败。
- 开发 wheel SHA-256：`56e45841582d8e764b53a78426e9a43171f2924aa86cd509a0a61419e5cd658f`。

## 边界

本项不实现 Task 创建服务、EgressAuthorization Owner、公开 HTTP 或真实外发。下一切片实现内部原子创建与可注入授权 Owner Port，正式 Egress 聚合未完成前仍失败关闭。
