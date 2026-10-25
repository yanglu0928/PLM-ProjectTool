# PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P03-P01：验证报告幂等重放前置核查

日期：2026-10-26。结果：`PRECHECK_COMPLETE_CR_PLAN_006_RECORDED`；无功能代码或数据库变更。

## 编码前检查

- 当前Phase：Phase 2 Platform Core。
- 当前WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P03-P01`。
- 输入基线：冻结API-04 `PLAN_VERSION_VALIDATE`、A06-P01/A06-P02、`plt_idempotency_receipts`、AuditEvent、0188 Plan append-only owner guards。
- 前置任务：Validate纯报告合同/评价器已通过后端完整回归；尚无持久事务Owner。
- 涉及模块：Plan-owned结果Schema/Migration、Audit与通用幂等收据引用。
- 涉及实体：固定PlanVersion报告、Audit事件身份、Project/Plan/Version/Actor复合范围。
- 涉及API：无；保持冻结200 ValidationReport。
- 涉及权限：结果必须仅能由未来受权Owner同事务写入；不能因结果记录存在而授予读取权限。
- 验收标准：能逐字段恢复首次报告和checked_at；Audit/结果/Receipt原子提交；不可变与安全回滚；来源后续变化不影响原回执重放。
- 风险：通用Receipt不含响应体、Audit只保留一个分类码；当前P01决定“No Validation table”无法满足首次报告重放。实现者不得用Audit.reason_code编码数组/计数或在重试时伪造首次结果。

## 变更处置

- 已登记 `CR-PLAN-006`，选择Plan-owned不可变验证报告结果表；追加Migration `20261026_0189`，原冻结`64cdf09`保持不动。
- A06-P01的初始L2建议“不增加Validation表”被后续幂等证据推翻；不变量是“不改变PlanVersion状态”，不是“禁止新增报告记录表”。修订决策追加记录于`docs/decisions/decision-log.md`。
- 本项仅完成前置核查及CR，没有ORM/Migration；下一项A06-P03-P02实现单一Migration与空/有结果历史降级保护，再由后续WBS实现Owner。

## 兼容与后续

- 数据迁移及升级/回滚尚未运行；新表不得单独部署，必须与Owner同批受控交付。
- Pilot/Gate/正式发行状态不变；Server 2025和Debian 13仍未在本项验证。
