# SOL-03-A06-P03-A03：Outline 当前覆盖证明前置复核

日期：2026-10-23。状态：`PRECHECK_PASS_WITH_DEPENDENCY`；本项只读核查，`coverage=UNAVAILABLE` 保持不变。

## 编码前检查

| 项目 | 结论 |
|---|---|
| 当前 Phase/WBS | Phase 2 / SOL-03-A06-P03-A03 |
| 输入基线 | Gate2冻结 DM-05/API-04；A06-P03-A01固定顺序与来源现时重证；A02旧阻塞记录；Section P13-P06正式Review/PG/Edge合成证据 |
| 前置 | Section当前Trace/Spec六维与正式批准指针已具备；Outline仍只有order/source两个现时维，覆盖原值不可用 |
| 涉及模块/实体 | solution、requirement、trace、review；OutlineVersion、SectionVersion、RequirementVersion、TraceLink、Review |
| 涉及API/权限 | 本片无API写入/Schema；后续同事务须当前Session/Project/License，精确固定版本/项目授权，不能借用测试角色放宽正式权限 |
| 验收标准 | 判定旧A02阻塞哪些已解除、哪些仍在，列出可独立编码的最小前置与负例；不把Section批准推成Outline覆盖PASS |
| 风险 | 只比对Outline固定需求子集会漏掉项目其他当前已批准需求；仅凭历史Section APPROVED无法证明当前Trace/来源仍有效；泛型missing声明不等于人工排除/延期决定 |

## 复核证据

1. `sol_sections.current_approved_version_ref` 现在由Section Review终态Owner写入，Section读仓储会校验同根/同项目、APPROVED、Review/Round非空。`SOL-05` 当前六维与精确 `IMPLEMENTS` 覆盖、固定Spec适配已可合成通过；A02“无正式Section批准/Trace/Spec”的原始阻塞已解除，不能再重复描述为缺失。
2. OutlineVersion只固定Section身份顺序和所列`requirement_refs`，不固定项目所有当前批准需求。现有 `OutlineVersionCurrentFactsService` 对`coverage`仍恒为`UNAVAILABLE`；`TraceImplementsCoverageService` 能核对**单个固定章节版本**的精确需求/ACTIVE边，但不能自行提供项目批准需求全集，也不核对多个批准章节的并集。
3. 冻结DM-05/API-04要求每个已批准RequirementVersion至少由一个正式章节覆盖，或有显式排除/延期决定。当前未发现可供Outline同事务调用的“项目当前批准RequirementVersion全集”受权Port，也没有把Outline `missing_declarations` 通用JSON转为可验证人工决定的正式Owner。不能只遍历Outline自报集合而宣称全覆盖；不能把泛型缺失声明当放弃需求的批准。

## 分片路线

- 下一片 `SOL-03-A06-P03-A04`：先实现受权、同事务、界限明确的项目当前批准RequirementVersion全集只读Port/Repository，含分页/容量上限或失败关闭、当前指针/Review/项目一致性，空集与竞态负例；不改Outline事实值或公开API。若现有Requirement读权限不足，先记CR/决策再实施。
- 随后独立片：逐Section当前批准指针/现时六维及Trace精确覆盖、Outline固定集合与批准需求全集逐项并集比对。无已验证排除/延期Owner时仅“所有已批准需求均覆盖”的安全子集可PASS，其他情况保持FAIL或UNAVAILABLE；不能静默丢弃Scope。
- 再完成Outline VALIDATE的持久Audit/幂等/HTTP/Windows与Review生命周期，之后返回Plan正式输入。Gate 3、Pilot、正式三平台发行不因此预先通过。

本片无程序/Schema/API/权限/数据变化；仅对冻结合同、当前应用/仓储与已验Section结果静态核查，未运行新的功能测试。回滚仅撤本记录/状态路线，不修改历史版本。
