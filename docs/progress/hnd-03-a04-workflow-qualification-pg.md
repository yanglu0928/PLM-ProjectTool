# HND-03-A04：Handover Workflow 资格真实 PG 验证

日期：2026-10-05。结论：`HND_03_A04_WORKFLOW_QUALIFICATION_PG_PASS`。环境：Windows 11、PostgreSQL 18.6；Debian 13 按用户指令不实机验证，Windows Server 2025 留目标环境矩阵。

## 验证范围与结论

- 在一次性空库迁移至当前 head 并执行 `alembic check`，实际创建 Handover Analysis/Version、PROJECT Review/Round 并批准为当前正式版本；Item 为 CONFIRMED，阻断 Item 的 Action 具备真实 OPEN→IN_PROGRESS→SUBMITTED→VERIFIED 事件链。
- 资格 Owner 通过真实 SQLAlchemy Repository 和各模块 Application Port 重证：物理 Document 字节、PROJECT Evidence、CURRENT_APPROVED Capability、SUCCEEDED GAP_ANALYSIS Task、精确 APPROVED ReviewRound，以及 VERIFIED Action 的响应 Document 和提交/验证 Evidence。
- `HANDOVER_ISSUES` 正例返回三条固定 Evidence 观测和精确 ReviewRound；同一事务内对 Handover Analysis/Version/Item/Action、Evidence、DocumentVersion、Review/Round 的竞争 `FOR UPDATE NOWAIT` 均返回 PostgreSQL `55P03`，证明当前事实共享锁保持至调用方事务结束。
- 调用前后对 Handover、Review、Document、Evidence、Capability、AI 的 29 张相关业务表做逐行逻辑快照，内容完全一致，证明资格调用没有业务写入；未用 PostgreSQL 元组活动统计代替逻辑内容证明，因为行锁本身会产生元组活动。
- 将来源 Evidence 变为 INELIGIBLE 后资格失败关闭；恢复后篡改 Action 响应文件的真实字节，资格再次失败关闭。测试库和临时文件均在 `finally` 清理，无客户数据、网络外发或生产迁移。

## 过程修正

首轮夹具依次暴露并修正了 Capability 声明计数、AI Task 必需输入引用、Action 事件/投影顺序和 VERIFIED 主体字段；这些都是验证夹具未满足现行数据库约束，不是生产绕过。最初采用 `pg_stat_xact_user_tables` 判断零写会把共享锁元组活动误计为写，因此改为相关业务表调用前后逐行逻辑快照，最终以全新隔离库完整重跑 PASS。

## 兼容、回滚与后续

本项只增加可重复验证脚本和追溯文档，不改 Schema/Migration、冻结 API、角色、配置、依赖、Secret 或业务数据。删除脚本即可回滚，A02/A03 生产合同与 Owner 不变。A04 只关闭 Handover 资格 Owner 的 Windows 11/PG18 真实验证，不代表 Workflow Checklist 已写入、Stage Transition、Gate 3、三平台发行或 UAT 通过。

下一项：`WFL-01-A07-P07-A01`，恢复 Workflow 受权 Checklist 追加命令的编码前检查，先限定 Handover 两项策略注册、当前 Evidence/Review 重证、Audit/幂等和同事务写边界；不把 Handover 适配器与通用 Workflow 写服务混为一个任务。
