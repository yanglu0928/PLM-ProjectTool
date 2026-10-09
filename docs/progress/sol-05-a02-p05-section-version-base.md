# SOL-05-A02-P05：SectionVersion 当前父级与版本序列基底

日期：2026-10-09。结果：`SECTION_VERSION_BASE_INTERNAL_PG_PASS`；仅同事务内部基底端口，0138 写闭锁未解除。

## 编码前检查

Phase 2 Platform Core；WBS `SOL-05-A02-P05`。输入 Gate2 冻结 DM-05/API-04、CR-SOL-003/0138、SectionVersion DRAFT 输入及 Document/Requirement/Evidence 前置证明。前置满足。涉及 Solution 的 Outline、Section、SectionVersion，只新增 Application 最小 DTO/Port 与 SQL 只读适配器；无公开 API、权限、Schema/Migration、依赖、配置或数据变化。验收：同项目 ACTIVE 父子、批准指针一致、父 Outline 先于 Section 独占锁、最新版本/前驱连续；缺失、跨项目、归档、断档/坏指针失败关闭。风险：内部证明被误称正式写入或完整历史链验证。

## 实施与验证

先读不可变 Section 父 ID 确定锁顺序，在调用者事务中锁父 Outline，再锁 Section，重验父子/项目/ACTIVE/批准指针/锁版本；共享锁最新 SectionVersion，计算下一版本号和固定前驱。首版必须无前驱；后续版必须有同 Section/Project 的前驱且版本号恰为上一号。未来写 Owner 必须在同一事务保持这些锁，并独立完成授权、License、来源、Trace、收据/Audit 与写 Guard；此端口本身不授予写入权限，也不证明整条历史链或 Review 有效性。

定向 pytest `7 passed, 16 subtests passed`，包括锁顺序 SQL、首版/续版、错项目/归档/坏批准指针/断档/溢出。Win11 可弃 PG18.6 `validation/sol-05-a02-p05-section-version-base/verify.py` 退出0：空库升至 head、Alembic drift、真实首版/续版、双项目隔离、父/章节归档与错误前驱拒绝。夹具使用单独临时库连接的 `session_replication_role=replica` 放入历史行，不代表生产写 Guard 已开放；正式 Guard 未更改。最终后端全量 pytest `3519 passed, 3 skipped, 5471 subtests passed`，退出0。

兼容/升级/回滚：纯新增未接线内部端口与验证资产；无 Migration/API/权限变化，删除增量代码可回滚，既有历史保持。正式目标账户/Server2025、性能、AI 质量、Gate3、SectionVersion 写 Owner/Review/Trace/Artifact 仍未验；Debian13 实机依用户指令跳过。下一项 `SOL-05-A02-P06` 组合有界 DRAFT 输入与同事务各项来源证明，仍不开放写入。

TraceLink：Gate2 DM-05/API-04 → CR-SOL-003/0138 → SOL-05-A02-P01～P04 → DEC-1171 → 本基底 → 组合输入证明 → Owner/Guard → VALIDATE/Review/Trace → Gate3。
