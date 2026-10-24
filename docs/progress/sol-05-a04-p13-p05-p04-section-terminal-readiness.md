# SOL-05-A04-P13-P05-P04：Section 客户批准前当前事实重证

日期：2026-10-23。状态：`INTERNAL_PASS`；不代表客户批准、Gate 3 或 Pilot 可用。

## 编码前检查

- 输入：Gate 2 冻结基线、CR-SOL-024、0183/0184 Section Review 受控状态、已验 P13-P05-P03 送审链。
- 单一问题：客户批准前，最新 `IN_REVIEW` SectionVersion 能否在同一事务以当前来源重新证明六维全 `PASS`，而不放宽送审 DRAFT 或公开 VALIDATE。
- 前置：送审实际 Session/PG 路径已验；Section 固定版本/指纹、Trace、Spec 当前资格端口现存。
- 范围：内部 Readiness、当前 Spec 资格/Validator 与最新版本共享锁。无 DB Schema、`/api/v1`、角色、License 权益变化。
- 主要风险：把旧送审 ready 当作客户批准时事实，或把 IN_REVIEW 意外开放给 DRAFT 送审及公开 VALIDATE。通过显式 `required_state` 与内部 `SectionCurrentFactQuery` 区分，并保持默认 DRAFT 关闭。

## 结果与证据

- 内部证明只接受明确的 DRAFT/IN_REVIEW；最新版本共享锁核对要求的状态，六维任何一维非 PASS 均拒绝。`SectionReviewReadinessProof` 带实际 `required_state`，不消费 VALIDATE Audit/收据。
- 固定 Spec 当前资格对 IN_REVIEW 可重新查询当前批准及 Review 精确快照；公开 VALIDATE 的 Spec 分支仍只接受 DRAFT。
- 定向测试 67 通过/27 子例；后端全量 3975 通过、3 跳过、6079 子例。
- 一次性 Windows 11/PostgreSQL 18.6 合成来源：真实 Session/Trace/Spec/Section 送审后，IN_REVIEW 六维重证全 PASS；默认 DRAFT 证明拒绝该版本；撤销 Trace 后新终态重证拒绝。复验脚本 `validation/sol-05-a04-p13-p05-p04-section-terminal-readiness-windows/verify.py` exit 0。

## 边界、兼容与回滚

- 这只提供终态 Owner 即将调用的内部证明，不创建 APPROVED/RETURNED/WITHDRAWN，不代客户作决定。终态 Review/Round 精确绑定、同事务状态变更、前端与真实客户确认仍待。
- 无迁移；代码可回滚至旧 DRAFT-only 内部证明，但不能删除已存在的评审历史。Pilot、Gate 3 和三平台 Release 继续 NOT_READY。
- 下一项：`SOL-05-A04-P13-P06-P01` 对照统一 Review Engine，接 Section 客户终态 Subject Owner 和受控 SQL 转移；批准必须调用此处 IN_REVIEW 六维重证。
