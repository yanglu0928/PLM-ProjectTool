# HND-01-A05-A05：Handover Version 业务原子送审

日期：2026-10-05。结论：`HND_01_A05_A05_SUBMIT_REVIEW_PASS`。下一项：`HND-01-A05-A06` 五个读取 HTTP 与三类独立签名 cursor。

## 实现边界

新增 Handover 外层送审 Owner 与可选 HTTP Router，复用 Review Owner 新增的通用 PROJECT 原子 create/start 持久化能力。外层固定 `HND-02`、`HANDOVER_ALL_V1` 和首轮，要求当前 ProjectManager、合格评审人、当前 Handover Version/来源/Action 完整性、License、Session/CSRF、Audit 和持久幂等均在同一 UOW 中通过。

同 Key 重放从不可变第一轮恢复原 201 响应，Review 后续批准也不改变首次回执；重放仍重验当前权限和 Subject 访问。默认应用不挂载 Router，Windows 生产组合留 A07。

## 偏差、兼容与回滚

按 CR-HND-006，冻结 DTO 的 `due_at/submission_note` 当前只接受 `null`，避免在无 Schema 字段时静默丢失业务事实。本项无 Migration、依赖、配置、Secret、外部网络或客户数据外发；回滚可撤可选 Router 和 Handover 编排，既有 Review/Audit/收据历史不删除。

首次真实库验证发现重放仓储假设应用固定 `submitted_at` 必须不早于数据库 `created_at`。两个时间来自不同受控时钟且冻结模型不保证该排序；已删除此无依据判断，保留 Review/Round/actor/版本和不可变首轮绑定校验，并以全新链重跑通过。该修正不放宽业务状态、授权或绑定约束。

## 客观验证

- 单元/合同定向 14 项通过：PROJECT 原子持久化、外层授权/幂等/死锁、默认关闭、严格 DTO、安全错误投影。
- Windows 11 / PostgreSQL 18.6：先注入 Review Audit 故障，证明 identity/round/version 状态整事务回滚；随后真实单命令送审、即时同 Key 重放、批准后原首次回执恢复、第二版送审与撤回通过；`alembic check` 无新操作。
- Windows 11 / Python 3.13 后端全量 2697 项通过，3 项环境条件跳过。
- 开发 wheel 包含并可导入四个新增 Handover/Review 模块，SHA-256 `6d368e45c0b15ce1488e3d03cf1f4f23db5b34281b5722ac92a545d8e768e83c`。

未完成：A06五读HTTP/cursor、A07 Windows真实组合与HTTP/PG；Server 2025、Debian 13、Gate 3和正式发行仍按总状态跟踪。
