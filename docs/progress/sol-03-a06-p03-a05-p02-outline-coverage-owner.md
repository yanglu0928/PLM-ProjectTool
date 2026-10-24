# SOL-03-A06-P03-A05-P02：Outline 当前批准章节覆盖证明

日期：2026-10-24。状态：`INTERNAL_UNIT_PASS`；本片仅实现内部同事务证明，不直接改变公开 VALIDATE 或持久 Audit。

## 编码前检查

| 项目 | 结论 |
|---|---|
| 当前 Phase/WBS | Phase 2 / SOL-03-A06-P03-A05-P02 |
| 输入基线 | Gate 2 冻结 DM-05/API-04；A04 当前批准 Requirement 全集受权有界证明；A05-P01 APPROVED Section Spec 内部重证；现有 Section 六维事实与精确 Trace IMPLEMENTS Owner |
| 前置 | Gate 2 已通过；A04/A05-P01 已完成；Section 当前批准指针/正式 Review 与六维/Trace 端口可复用 |
| 涉及模块/实体 | solution、requirement、review、trace；OutlineVersion、SectionVersion、RequirementVersion、Review/Round、TraceLink |
| 涉及 API/权限 | 无新公开 API/Schema；在调用者事务中先由库存服务验证 License、Session、`REQ_VERSION_GET` 项目授权；Section/Review/Trace 仅通过已授权内部端口读取，缺口失败关闭 |
| 验收标准 | Outline 固定需求集合与项目当前正式批准需求全集相等；每个固定 Section 同 Outline/项目、当前批准版本及正式 Review 精确匹配，六维现时 PASS，逐章节 Trace 与固定需求精确一致；并集恰好覆盖全集。空/超限、缺章节批准、错项目/Review、旧版本、缺/多 Trace、需求遗漏、并发漂移不得 PASS |
| 风险 | 现有 `missing_declarations` 为泛型 JSON，不是正式排除/延期决定；本片不以其减少 Scope。Section 非需求正文允许零引用的建模空间，但当前六维 Trace Owner 对空集合不可证明；本片将其标为不可用，不伪造已覆盖，后续需独立兼容设计与测试 |

决策：建立内部 Coverage Owner，先做完整需求库存授权与锁定，再读取固定 Section 当前批准版本/正式 Review 和六维现时事实，最后比对不可变 Outline refs 与当前全集及 Section 并集；不再实现第二套 Trace 扫描。失败时保持 Outline `coverage=UNAVAILABLE` 或后续调用者按已知缺口映射 FAIL，不保存半成品。本片无数据迁移；可撤未装配的内部 Owner，历史不变。只有后续独立完成调用者接线、Windows/PG/HTTP 与 Review/UAT 验证，才改变公开 coverage/Gate 结论。

## 验证与边界

- 新增内部 Owner 定向 7/7，通过同事务同查询身份、项目完整需求全集、两章并集/重复覆盖、泛型缺失声明无豁免、缺口/范围外版本、未批准或错项目章节、错误 Review/指纹、Trace FAIL、Spec UNAVAILABLE 和未授权拒绝。
- 关联定向 48/48，后端全量 `3998 passed, 3 skipped, 6079 subtests passed`。无 Schema/API/Migration 变更。
- 本片端口单元测试用合成返回值验证编排；A04 的真实 PostgreSQL 项目锁/容量证明、已有 Section/Trace/Review 的各自真实验收不能替代**本服务的完整 PG 组合验收**。因此仅标 `INTERNAL_UNIT_PASS`，下一片接入 Outline 调用者并安排 Win11 一次性 PG 完整/缺口/竞态复验；Outline `coverage` 仍为 UNAVAILABLE，Gate/Pilot/正式发行不变。
