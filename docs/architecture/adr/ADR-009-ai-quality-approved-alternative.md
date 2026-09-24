# ADR-009：POC-03 质量失败的批准替代控制

## Status

`ACCEPTED_EXCEPTION / GATE_3_AND_UAT_BLOCKER`

## Date

2026-09-22

## Context

POC-03 在 50 条独立留出集上的真实结果为：Top-5 49/50（98.00%）PASS，分类 24/50（48.00%）与精确引用 37/50（74.00%）FAIL，低于分类 90% 和引用 98% 门槛。R10 诊断发现能力适配缺少标准能力双来源对照，引用存在首位偏差；R11 已形成双来源证据、Prompt v3 和 Evidence Selector 的离线合同，但没有新的独立真实质量通过证据。

用户通过 `EXC-P0-006` 批准以替代控制关闭 Phase 0 Gate 1，同时明确不得重写失败结果或降低门槛。

## Decision

1. 永久保留 98.00% / 48.00% / 74.00% 历史证据；分类与精确引用继续标记 FAIL。
2. 所有 AI 分类、引用、需求、方案、计划和输出建议固定为 `SUGGESTION / NOT_FORMAL_FACT`，不得自动升级为正式业务事实。
3. 能力适配任务采用 R11 双来源 Context：需求/约定证据与标准能力证据必须显式分组；Prompt v3 使用结构化输出和受控五类结论。
4. Evidence Selector 依据问题支持度选择引用，不以 Reranker 第 1 名作为默认答案；引用必须位于已授权 Context 并指向不可变 DocumentVersion/Evidence Locator。
5. ReviewService 对 AI 建议形成的正式对象强制人工确认；送审锁定、退回意见、升版重审和历史确认规则不因 AI 置信度而豁免。
6. 当前 50 条已成为已见测试集，不能再次作为“独立留出集通过”证据，也不能逐条写规则后重新宣称泛化质量。
7. Gate 3 和 UAT 前必须使用未参与 Prompt/规则/标签调优的新独立留出集，重新验证分类 ≥90%、精确引用 ≥98%，并保留 ProjectId、越界引用和失败关闭检查。
8. 新一轮客户数据发送至百炼、DeepSeek 或其他外部目的地前，仍需当轮明确授权；授权不得从历史批次外推。

## Consequences

- Architecture/Data/API 冻结可以继续，Phase 0 不因当前质量失败永久停滞。
- 平台必须把人工确认实现为不可绕过的业务控制，而非 UI 提示。
- Gate 3/UAT 在新独立留出集达标前保持阻塞；格式/Schema 正确、链路成功或人工确认存在均不能替代质量门槛。
- 需要额外的 Review、Evidence、Prompt/Index 版本和质量审计数据模型。
- 生产环境不能宣传自动分类或自动引用已达到目标准确率。

## Rejected Alternatives

- 把 48.00% / 74.00% 改写为通过：违背真实证据。
- 降低 90% / 98% 门槛：用户未授权，且会掩盖质量风险。
- 在当前 50 条上逐条调规则并复测：产生数据泄漏，不能证明泛化。
- 仅用人工确认替代后续质量验证：控制风险但不证明模型能力。

## Rollback / Change Rule

本 ADR 的历史失败证据不可删除或覆盖。可以回退 R11 实现并恢复为完全人工流程，但在新独立留出集达标前不得取消 Review 强制确认。降低门槛、允许 AI 自动正式化或免除新留出集属于 L3/正式 Gate 决策。

## References

- `docs/poc/phase-0-exceptions.md`：EXC-P0-006
- `docs/progress/phase-0-summary.md`
- `poc/poc-03-rag/` R10/R11 证据
