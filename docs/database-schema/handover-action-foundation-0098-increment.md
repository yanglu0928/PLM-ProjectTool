# Handover Action Foundation Schema 0098 增量

日期：2026-10-05。迁移：`20261005_0097 -> 20261005_0098`。范围：HND-03 `ActionItem` Root、固定响应文档、Evidence 和不可变状态事件；本项不开放 HTTP 或完整生命周期 Owner。

## 物理结构

- `hnd_action_items`：PROJECT Root；支持固定 `ANALYSIS_ITEM` 来源或明确 `HUMAN` 来源、六类动作、requested input、Owner、due_at、priority、状态投影、验证人/时间、resolution Trace、人工创建原因和强锁版本。
- `hnd_action_response_refs`：固定 PROJECT DocumentVersion 响应集合，按 Action 内 ordinal 排序。
- `hnd_action_evidence_refs`：固定 Evidence 集合，以 SUBMISSION/VERIFICATION/RESOLUTION 区分用途。
- `hnd_action_state_events`：append-only 状态事件，保存序号、前后状态、Actor、reason、UTC 与 trace_id。

## 约束与 Owner 边界

Schema0098只允许 Action OPEN/v0 与唯一 seq0 `NULL -> OPEN` 事件在同一事务建立；Actor/reason必须与 Root 创建事实一致，due_at不得早于创建时间。根据CR-HND-002，人工创建可引用同项目 DRAFT/CANDIDATE Item；既有 APPROVED/CONFIRMED Item同样可引用。跨项目、错误状态、无初始事件、UPDATE/DELETE/TRUNCATE及响应/Evidence提前写入均失败关闭。

响应、提交、验证、关闭、取消和可变投影仍由后续 Owner Migration 精确开放；当前四表存在不代表完整Action流程已可用。Schema不自动确认Item、不自动创建Action、不把SUBMITTED等同CLOSED。

## 升级、回滚与验证

增量只新增四表、索引、外键和守卫，不修改冻结URL、角色、依赖、网络或客户数据。空Action历史可降回0097并重升；有任一Root/child/event历史后拒绝降级，要求向前修复或从已验证备份恢复。离线SQL downgrade无法证明历史为空，固定拒绝。

Windows 11/PostgreSQL 18.6 已完成空库降升、drift、候选Item人工来源、初始事件、跨项目/生命周期负例和历史拒降；既有pgvector表达式与计算默认值比较器警告不构成新增drift。
