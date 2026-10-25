# CAP-02-A05-P04-P03-A02-P02：GLOBAL Capability Review 内部决定

日期：2026-10-24；状态：`INTERNAL_UNIT_PASS / PG_AND_HTTP_PENDING / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `CAP-02-A05-P04-P03-A02-P02`，只做 CAP-01 GLOBAL Review 内部决定命令与冻结 Reviewer 资格纠偏。|
|基线与前置|`CR-CAP-005`、冻结 Capability Subject 决策 `DEC-20261005`（送审者为 DeploymentAdmin，Reviewer 当前启用）、既有 GLOBAL Review 持久化/终态 Capability Owner、当前 Session/License/幂等收据。|
|数据/API|不改 ORM、Schema、Migration、公开 API 或既有 PROJECT Review；内部命令尚未 Windows 装配。|
|安全/原子性|当前受分配且已启用 Reviewer 才可决定；精确 CAP-01/GLOBAL/策略/轮次，RETURN 需实质意见；同 Key 正文指纹、当前访问重证、Review+Capability+Audit+收据同 UOW；源撤销导致终态失败整笔回滚。|
|验收|定向正负/重放测试、前后端全量回归和构建；隔离 PG、HTTP、浏览器及产品批准另片验。|

新内部服务校验 Session/CSRF、License、CAP-01 Scope 与本轮 Reviewer；幂等范围 `project_id=None`，回放依据原事件重建决定回执并复查 Reviewer 与 Subject 当前历史访问，不再写第二次决定。首次决定调用既有 `GlobalReviewPersistenceService`，由 Capability Subject 在终态重证来源并原子消费批准/退回。新服务不自己直写 Review/Capability 表。

编码前发现 P04-P02 前端及 CR 初稿错误地把 Reviewer 限定为 DeploymentAdmin；冻结决策仅要求当前启用的受分配用户。已在 `CR-CAP-005` 追加纠偏条款，修订候选页为所有已启用用户、只读服务允许受分配的普通用户，决定服务采用现有 Auth Session/CSRF 当前用户证明，不让任意未分配用户决定。原误判仍可从先前 Git 提交追溯。

验证：内部读取/决定定向 17/17；后端单元全量 3483 通过/3 跳过/4798 子例，前端全量 1938、typecheck/build 通过。定向首轮 1 项失败因 Mock 默认返回值不是 `None`，修正夹具后 15/15，再加普通评审人读取等用例为 17/17；未修改产品逻辑掩盖。当前仅端口级单元测试，未做隔离 PostgreSQL 原子提交/回滚、公开 HTTP、Windows/Edge、真人批准或正式信任；Gate/Pilot/Release 仍未通过。
