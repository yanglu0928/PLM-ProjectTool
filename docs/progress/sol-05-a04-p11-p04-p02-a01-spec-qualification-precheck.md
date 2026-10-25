# SOL-05-A04-P11-P04-P02-A01：固定 SpecVersion 资格证明编码前检查

日期/版本：2026-10-23 / `0.1.0-dev.0`。状态：`WINDOWS_INTERNAL_PASS`；仅资格证明，`FIXED_REFS` 写入口继续 503。

|项目|结论|
|---|---|
|Phase/WBS|Phase 2 / `SOL-05-A04-P11-P04-P02-A01`，单一问题是证明既存固定 SpecVersion 可作为新 SectionVersion 的候选引用|
|输入基线|Gate 2 DM-05/API-04、CR-SOL-022 的有向版本谱系、DEC-20261023-1203；当前 0179 根仅允许 NONE_REQUIRED，SpecRef 子表仍闭锁|
|前置|SOL-06 固定版本/Review、SectionVersion 不可变读取/当前创建基底、Review Snapshot 公共读取接口存在；不得要求双方同版本互指|
|涉及模块/实体|Solution 的 SpecVersion、SectionVersion/Section 根及版本链；只通过 Review Application Interface 读取批准快照|
|API/权限|本项无公开 API 或写入；未来由已授权 Section CREATE 调用，ProjectId 严格固定、无独立越权入口|
|验收|同项目且为 SpecSeries 当前 APPROVED、Review/轮次与固定内容指纹一致；Spec 来源包含本 Section 的祖先版本且未退回/受限；Spec 与来源章节/新章节至少共享一个固定需求版本（允许跨章节 Spec 另含其他需求）；撤销/替代/错项目/错来源/损坏链失败关闭；单元与隔离 PG 证据|
|风险|仅靠 FK/历史 APPROVED 状态会把已替代、Review 不一致或其他章节的 Spec 固化；只靠“最新 SectionVersion”又会造成不可变双向创建死锁|

资格仅表示“可以作为候选固定引用”，不是 Spec 内容对新正文的语义适配、章节客户确认或 VALIDATE 的 `spec=PASS`。`FIXED_REFS` 写入口在本片继续 503，闭合子集合 Owner/Guard 后续单独验收。无 Schema/API/权限变更；回滚可移除未接入的只读证明。方案细节登记 `DEC-20261023-1204`。

## 实施及独立验收

- Solution 内部只读资格服务以同一事务核对当前唯一批准 Spec、精确 Review 身份/批准轮次/固定内容指纹、同项目来源 Section 祖先链与三个集合共有的固定 RequirementVersion；Review 仅通过其公开快照 Port 读取。任何端口错误、缺失、错项目/Series/来源、已替代/退回或不完整证据均统一失败关闭，不泄漏正文。
- Win11/一次性 PostgreSQL 18.6 复用真实 SOL-06 创建、送审及统一 Review 批准链，在实际批准快照上证明合法候选，并实测被替代 Spec、跨项目引用、无关祖先拒绝。输出 `SOL_05_A04_P11_P04_P02_A01_SPEC_QUALIFICATION_PASS`；此为合成来源/测试信任，不等于客户真实 Review。
- 定向单元 5 项/23 子例通过；后端完整回归 `3900 passed, 3 skipped, 6061 subtests passed`。无迁移、公开 API 或前端变化；已有 0179 和旧客户端行为保持。

已知问题与下一项：证明尚未装配到 `FIXED_REFS` 的 Section CREATE；`SOL-05-A04-P11-P04-P02-A02` 需把闭合子集合 Guard/Owner、固定引用指纹/收据/Audit 与资格重证装入同一写事务，再验真实 HTTP/PG。新章节正文的语义适配、客户确认、Section/Outline Review、正式信任与 Gate/Pilot 仍未通过。
