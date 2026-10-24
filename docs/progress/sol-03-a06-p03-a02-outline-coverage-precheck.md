# SOL-03-A06-P03-A02：Outline 当前覆盖证明前置核查

日期/版本：2026-10-23 / `0.1.0-dev.0`。状态：`PRECONDITION_BLOCKED`；已验顺序/来源重证保留，coverage 不改为 PASS。

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-03-A06-P03-A02`|
|输入基线|冻结 DM-05 的 Outline/Section 独立 Review 与正式输出固定版本，API-04 `SOL_OUTLINE_VERSION_VALIDATE` order/source/coverage，A06-P03-A01 当前来源重证|
|前置任务|同项目已批准 SectionVersion 的固定集合、其 RequirementVersion 精确覆盖/显式排除、当前 ACTIVE `IMPLEMENTS` TraceLink 及正式 Review 证明|
|涉及模块/实体|solution、trace、review；本项仅核查已存在的 Application Port/Schema/Owner，不改数据库|
|API/权限|不挂载 HTTP；后续每个 Section/Requirement/Trace 仍需现时项目成员、Session、License 与固定版本证明|
|验收标准|确定能否在同一事务对 Outline 固定章节顺序逐项证明正式章节与需求覆盖；不能时列出可独立推进的上游片|
|风险|把 DRAFT SectionVersion、历史 VALIDATE 或纯外键当 Approved；未逐边验证 Trace；零引用时默认覆盖通过|

## 当前代码证据与结论

1. `TraceImplementsCoverageService` 已具 SOL-05/SOL-06 固定目标与 REQ-03 精确 ACTIVE 边证明，`SectionVersionTraceOwner` 已有受权读取；但 `SectionVersionCurrentValidator` 的 `trace` 和 `spec` 维仍显式返回 `UNAVAILABLE`，Windows 组合也尚未给它注入 Trace 当前证明。
2. SectionVersion 有 DRAFT 创建、历史读取和前四维现时 VALIDATE；没有 `SOL_SECTION_VERSION_SUBMIT_REVIEW`、终态 Subject Owner 或受 Review 绑定的 Approved SectionVersion。当前 ORM/迁移也没有冻结模型要求的 SectionVersion 固定 StructuredSpec 引用表，不能从 SOL-06 专项批准自动推定章节批准。
3. Outline 固定的是 Section *身份*，不是每个已批准 SectionVersion；正式输出还需固定并授权读取 SectionVersion/StructuredSpecVersion。因此目前没有能给 Outline coverage 产生可信 PASS 的完整上游 Port。本任务前置未满足，不实现“恒 PASS”或仅以 DRAFT Trace 边的弱覆盖。

## 转向不受阻塞任务

- 先执行 `SOL-05-A04-P10-P01`：将已验的统一 `TraceImplementsCoverageService` 接入 SectionVersion 当前验证的 Trace 维，精确要求固定 RequirementVersion 全集、同项目/同事务/现时权限，缺边或失效失败关闭；不改 Spec 维或 Review 状态。
- 随后独立补齐 SectionVersion 固定 Spec 引用及当前资格、正式 Review/批准链，再回到本 Outline coverage Owner；此顺序不放宽冻结 API/Gate。若输入/Schema 的兼容调整会触及冻结合同，先记录 Change Request、迁移/回滚/验证计划再实施。

验证方式：冻结合同与 Trace/Section 应用、Windows 组合、ORM/迁移静态交叉核查；无程序/Schema/API/权限/数据变更，未运行功能测试。正式信任、Gate 3、Pilot、Release 继续未通过。
