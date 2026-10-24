# SOL-03-A06-P04-P03-A01：Outline评审阶段内部现时查询

日期：2026-10-24。状态：`PASS`（内部查询/单元合同；未装配真实Subject）。

## 编码前检查

| 项目 | 结论 |
|---|---|
| 当前Phase/WBS | Phase 2 / `SOL-03-A06-P04-P03-A01` |
| 输入基线 | 冻结API-04 Outline VALIDATE/SUBMIT_REVIEW；统一Review固定送审合同；DEC-1221 |
| 前置 | Outline三维真实PG DRAFT证明及0185状态窄门已验；完整Subject Owner仍待本片后续A02 |
| 涉及模块/实体 | solution内部只读现时事实与覆盖Owner；无数据实体变化 |
| 涉及API/权限 | 不修改公开`:validate`、用户角色或CSRF；内部查询由将来的受权Review事务调用 |
| 验收标准 | 内部DRAFT/IN_REVIEW使用固定版本/同事务三维重证；公开VALIDATE保持原DRAFT限制；错身份、来源缺口、未知来源不PASS；定向/全量回归 |
| 风险/回滚 | 不以历史VALIDATE报告代替当前事实；不在此片创建Review、改状态或开放HTTP；撤内部查询可恢复原行为 |

本片只打通后续Subject的事实查询前置，不宣称正式送审可用。

## 实施与验收

- 新增内部`OutlineCurrentFactQuery`，只包含真实Session令牌、Trace、Project/Outline/固定Version身份，不接受客户端幂等Key或伪造CSRF；其调用方必须先完成Session、License、Project和Review授权并保持同一事务。
- Outline现时来源/覆盖Owner接受该内部查询，`DRAFT/IN_REVIEW`均可重新证明；公开`ValidateOutlineVersion`仍只在`DRAFT`取得覆盖证明。来源与覆盖仍须三维精确匹配；未知来源、错项目或错版本失败关闭。无Schema/公开API/权限变化。
- 定向21项通过（内部IN_REVIEW覆盖、相同事务对象、公开非DRAFT拒绝、错身份和未知来源）；后端全量`4016 passed, 3 skipped, 6107 subtests passed`。本片没有真实PG内部Subject装配，故不宣称正式送审或客户终态已验。

下一片`SOL-03-A06-P04-P03-A02`建立Outline Review Subject的最新版本锁、确认人资格、固定快照与真实送审/终态Owner接口。内部查询可以撤除且不修改已存历史；Pilot/Gate仍未通过。
