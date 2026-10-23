# SOL-05-A04-P11-P01：SectionVersion 固定 StructuredSpec 关联前置核查

日期/版本：2026-10-23 / `0.1.0-dev.0`。状态：`DESIGN_CONFLICT_RECORDED`；已建立 `CR-SOL-022`，本项未改程序或数据库。

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-05-A04-P11-P01`|
|输入基线|冻结 DM-05/API-04 的 `SolutionSectionVersionInput.structured_spec_refs`、StructuredSpec 的固定 SectionVersion 来源、CR-SOL-003 时序补充；现有 Section/Spec 创建及 Review/Trace 实现|
|前置任务|SOL-06 版本、类型校验及独立 Review 已具内部/Windows 验收；SectionVersion 当前 Trace 已在 Windows/PG 验收；Section 固定 Spec 物理引用与声明尚未存在|
|涉及实体|SectionVersion、固定 SpecVersion 引用、StructuredSpec 的固定 SectionVersion 来源；旧版本/首响必须保留|
|涉及 API/权限|冻结 `/api/v1` CREATE/VALIDATE/Review 路径不变；只能作可兼容的可选输入扩展；正式用户对“无需专项”作显式声明，AI 不得自动确认|
|验收标准|确定无循环创建的语义、历史未声明与明确空集合区分、固定引用/同项目/版本资格、无数据丢失迁移与回滚及独立验收顺序|
|风险|缺字段被当“无需专项”、旧 DRAFT 自动变可送审、双方互相要求同一精确版本导致创建死锁、引用旧 Spec 但其来源已漂移|

## 代码与合同交叉核查

1. 冻结模型列出 SectionVersion 的 `structured_spec_refs`，但当前 `SectionVersionDraftInput`、CREATE HTTP 与 ORM/迁移没有该集合；Section 当前验证 `spec=UNAVAILABLE`。`StructuredSpecDraftInput.section_refs` 则强制至少一个固定 SectionVersion，并允许来源为最新 DRAFT/IN_REVIEW 或当前 APPROVED。
2. 如果 SectionVersion 创建时强制非空 SpecVersion 且 SpecVersion 创建时强制引用同一个 SectionVersion，现有两个独立 POST/不可变版本无法产生首对对象；事后补引用会改写已冻结版本。这是实施语义冲突，不可用空 UUID、延迟 FK 或假 APPROVED 绕过。
3. `CR-SOL-022` 选择单向、可分期的显式声明：新 SectionVersion 在创建时声明“无需专项”并给出理由，或固定已存在的 SpecVersion 集合；未提供声明的旧/兼容请求仍可产生 DRAFT，但状态为 `UNDECLARED`，绝不自动使 `spec` PASS。Spec 可独立引用已存在的 SectionVersion，独立 Review；正式输出再固定双方已批准的版本，不要求同一对版本互相回指。
4. 固定 Spec 集合的资格、同项目/同 Section 适用性、当前批准/来源漂移必须在后续 Owner 同事务重证；本项不宣称非空分支可用。“无需专项”也只是待评审人工声明，不能代替客户 Review。

## 顺序

`P11-P02` 增量闭锁 Schema/ORM 与可逆空/有数据升降；`P11-P03` 可兼容输入/响应、旧版本 `UNDECLARED` 反读；`P11-P04` 新版本写 Owner/Guard/PG；`P11-P05` 现时 Spec 资格与 VALIDATE；之后独立完成 Section Review、Outline coverage/Review 和 Plan。每步保持无客户数据外发、旧历史不可覆写、Gate/Pilot/Release 未通过。

验证方式：冻结合同、现有模型/迁移、CREATE/VALIDATE/Spec Review 当前代码静态交叉核查；本片无程序、Schema/API、权限、数据变化，未运行功能测试。
