# CR-HND-002：Handover ActionItem 与 Review 顺序闭环

日期：2026-10-05。状态：依据 `CR-EXEC-001` 持续授权批准实施。Gate 2 原冻结提交 `64cdf09` 保留；本 CR 只澄清 HND-02/HND-03 的运行顺序与正式化边界，不新增 Root、公开 Operation、角色或业务 Scope。

## 冲突

冻结 DM-05 要求资料缺失必须创建 ActionItem，并将 ActionItem 的来源描述为“已确认分析项或明确人工来源”；冻结 API-04 又允许项目成员从 source item 人工创建 ActionItem，并要求资料缺失用显式 flag 加 ActionItem。当前 Schema0097 中所有 Draft Item 初始均为 `CANDIDATE`，而只有 Review 终态才能把版本和 Item 正式化。

若坚持“Item 已确认后才能建 Action”，Review 送审前无法证明每个 `source_missing` / `NEED_CONFIRM` 已有待办承接；若先批准再补待办，则会出现已正式化但无法追踪的缺资料/待确认项。自动在 Review 终态创建 Action 也缺少 Owner、期限、类型及人工 reason，违反“AI 不得创建正式 ActionItem”和明确人工来源约束。

## 选择

1. ProjectManager 或 ImplementationMember 可通过既有 `HND_ACTION_CREATE`，以明确 actor/reason 从同项目固定 DRAFT Version 的 `CANDIDATE` Item 创建正式 ActionItem；这只证明人工登记待办，不确认 Item 内容、不改变 Version/Item 状态。
2. 上述前置仅用于解除顺序死锁。Action 必须保存固定 `source_analysis_version_ref + source_item_id`、创建人、创建原因、requested input、Owner、期限和优先级；跨项目、动态最新版、AI自动创建或缺人工 reason 一律拒绝。
3. Handover Review 送审前，每个 `source_missing=true` 或 `item_type=NEED_CONFIRM` 的 Item 必须存在同源且未被无替代取消的 ActionItem。Action 可以处于 OPEN/IN_PROGRESS/SUBMITTED/VERIFIED/CLOSED；Review批准只确认问题清单，不把开放 Action 当作已解决。
4. Review APPROVED 时，目标 Version 进入 APPROVED，当前正式指针原子更新，目标 Version 内 `CANDIDATE` Item 受控投影为 `CONFIRMED`；RETURNED/WITHDRAWN 保持 Item 为 CANDIDATE。RESOLVED/ACCEPTED_RISK 等结果只能来自后续人工动作、Evidence/Trace 与新版本，不由 AI 或批准动作推断。
5. Workflow/Gate 仍只消费满足规则的 VERIFIED/CLOSED Action；SUBMITTED、Review APPROVED 或 Item CONFIRMED 均不等于问题关闭。

## 实施顺序调整

`HND-01-A04-A01` 完成 Review 前置核查后，先进入 `HND-02-A01` 物理化 HND-03 ActionItem 及状态历史，再实现 Action 创建/状态 Owner；随后返回 `HND-01-A04-A02` 实现 Handover PROJECT Review Subject、送审和终态消费。该调整替代 CR-HND-001 原先“先完整 A04、后 HND-02”的批次顺序，但保留其其余约束。

## 影响、迁移与回滚

不修改冻结 URL、DTO 资源族、角色矩阵或 Review 通用规则。后续 Schema 增量必须同时验证 DRAFT source item 人工建 Action、Action 前置核验、Review 与正式指针原子性、退回/撤回、开放 Action 不关闭 Workflow，以及历史拒降。

应用回滚通过不装配 Action/Review Owner 停止新写；合法 Action、Review、Audit、Trace 与版本历史不删除。没有客观 Action/Review 证据时不得标记正式 Handover、关闭 Gate 3 或声称客户已确认。
