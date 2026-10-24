# SOL-03-A06-P03-A05-P01：已批准章节的现时 Spec 只读重证

日期：2026-10-24。状态：`UNIT_PASS`。本片只解决 Outline 覆盖前置的已批准 Section Spec 重证，不计算覆盖并集。

## 编码前检查

| 项目 | 结论 |
|---|---|
| 当前 Phase/WBS | Phase 2 / SOL-03-A06-P03-A05-P01 |
| 输入基线 | Gate 2 冻结 DM-05/API-04、Section 六维校验和正式 Review；A04 已受权需求全集 |
| 前置 | 已批准 Section 当前指针/Review 存在；`SectionVersionCurrentValidator` 可内用现时事实，但 `_spec_status` 与 Spec `prove_current` 只接受 DRAFT/IN_REVIEW |
| 涉及模块/实体 | solution SectionVersion、固定 StructuredSpecVersion/Review；只读应用证明 |
| 涉及 API/权限 | 不改公开 `/api/v1` 或权限；只有内部 `SectionCurrentFactQuery` 可对 APPROVED 重证，公开 `ValidateSectionVersion` 仍不因此批准非草稿 |
| 验收标准 | APPROVED + `NONE_REQUIRED` 有界理由或 `FIXED_REFS` 当前资格能正常重证；Spec 替换/来源失效失败关闭；公开 VALIDATE 对已批准版继续返回 UNAVAILABLE |
| 风险 | 扩大 `prove_current` 输入状态若误传播到公开 VALIDATE，会让旧批准内容被重新当草稿送审；按查询类型限定，并保持后续正式 Review 指针另验 |

这是内部只读状态范围补足，不新增 Scope、Schema 或 Breaking API。失败时回退本片内部状态分支，不改不可变业务历史；A05 后续片仍须在同一事务验证 Section 当前批准指针/Review/六维及 Trace 并集，Outline coverage 维本片保持 UNAVAILABLE。

## 验证

- 定向 `test_section_structured_spec_qualification.py` 与 `test_solution_section_version_validate.py`：40 通过、27 子例。涵盖已批准固定 Spec 现时资格与替换失效、已批准 NONE_REQUIRED 理由正反例，以及内部查询可重证而公开 VALIDATE 仍 UNAVAILABLE。
- 后端全量 `3991 passed, 3 skipped, 6079 subtests passed`。本片未改数据库或公开 API；真实 PostgreSQL 的已批准章节整链/Review/Trace 并集留给后续片验证，不借本片推断正式客户确认或 Outline coverage PASS。
